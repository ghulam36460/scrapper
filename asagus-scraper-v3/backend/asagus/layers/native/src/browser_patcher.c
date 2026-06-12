/*
 * Native Browser Patcher - C Implementation
 * =========================================
 * Low-level browser memory patching to remove automation markers.
 * 
 * Features:
 * - Direct process memory manipulation
 * - Patch browser before JS initialization
 * - Remove CDP/devtools detection markers
 * - Platform-specific memory protection handling
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#ifdef _WIN32
    #include <windows.h>
    #include <psapi.h>
    #define EXPORT __declspec(dllexport)
#elif __APPLE__
    #include <mach/mach.h>
    #include <mach/mach_vm.h>
    #define EXPORT __attribute__((visibility("default")))
#else
    // Linux
    #include <sys/ptrace.h>
    #include <sys/wait.h>
    #include <unistd.h>
    #define EXPORT __attribute__((visibility("default")))
#endif


/*
 * Signatures to patch (automation detection markers)
 */
const char* AUTOMATION_SIGNATURES[] = {
    "webdriver",
    "__webdriver_evaluate",
    "__selenium_evaluate",
    "__webdriver_script_fn",
    "driver-evaluate",
    "__driver_evaluate",
    "__webdriver_unwrapped",
    "__fxdriver_evaluate",
    "__driver_unwrapped",
    "webdriver-evaluate",
    "selenium-evaluate",
    "__Selenium_IDE_Recorder",
    "_Selenium_IDE_Recorder",
    "callSelenium",
    "_selenium",
    "$cdc_",
    "$chrome_asyncScriptInfo",
    "__$webdriverAsyncExecutor",
    NULL
};


#ifdef _WIN32
/*
 * Windows implementation using ReadProcessMemory/WriteProcessMemory
 */
EXPORT int patch_browser_process_win(DWORD pid) {
    HANDLE hProcess = OpenProcess(
        PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
        FALSE,
        pid
    );
    
    if (hProcess == NULL) {
        fprintf(stderr, "Failed to open process %lu: error %lu\n", pid, GetLastError());
        return -1;
    }
    
    printf("Opened browser process %lu for patching\n", pid);
    
    // Get process memory regions
    MEMORY_BASIC_INFORMATION mbi;
    unsigned char* addr = NULL;
    int patches_applied = 0;
    
    while (VirtualQueryEx(hProcess, addr, &mbi, sizeof(mbi)) == sizeof(mbi)) {
        // Only patch committed, readable memory
        if (mbi.State == MEM_COMMIT && 
            (mbi.Protect == PAGE_READWRITE || 
             mbi.Protect == PAGE_EXECUTE_READWRITE)) {
            
            size_t region_size = mbi.RegionSize;
            if (region_size > 1024 * 1024 * 100) {  // Skip regions > 100MB
                addr = (unsigned char*)mbi.BaseAddress + mbi.RegionSize;
                continue;
            }
            
            unsigned char* buffer = (unsigned char*)malloc(region_size);
            if (!buffer) {
                addr = (unsigned char*)mbi.BaseAddress + mbi.RegionSize;
                continue;
            }
            
            SIZE_T bytes_read;
            if (ReadProcessMemory(hProcess, mbi.BaseAddress, buffer, region_size, &bytes_read)) {
                // Search for automation signatures
                for (int i = 0; AUTOMATION_SIGNATURES[i] != NULL; i++) {
                    const char* sig = AUTOMATION_SIGNATURES[i];
                    size_t sig_len = strlen(sig);
                    
                    for (size_t j = 0; j < bytes_read - sig_len; j++) {
                        if (memcmp(buffer + j, sig, sig_len) == 0) {
                            // Found signature, patch it
                            printf("Found signature '%s' at offset %zu\n", sig, j);
                            
                            // Replace with null bytes
                            memset(buffer + j, 0, sig_len);
                            
                            // Write back
                            SIZE_T bytes_written;
                            DWORD old_protect;
                            VirtualProtectEx(hProcess, 
                                           (unsigned char*)mbi.BaseAddress + j,
                                           sig_len,
                                           PAGE_EXECUTE_READWRITE,
                                           &old_protect);
                            
                            WriteProcessMemory(hProcess, 
                                             (unsigned char*)mbi.BaseAddress + j,
                                             buffer + j,
                                             sig_len,
                                             &bytes_written);
                            
                            VirtualProtectEx(hProcess,
                                           (unsigned char*)mbi.BaseAddress + j,
                                           sig_len,
                                           old_protect,
                                           &old_protect);
                            
                            patches_applied++;
                        }
                    }
                }
            }
            
            free(buffer);
        }
        
        addr = (unsigned char*)mbi.BaseAddress + mbi.RegionSize;
    }
    
    CloseHandle(hProcess);
    printf("Applied %d patches to browser process\n", patches_applied);
    
    return patches_applied > 0 ? 0 : -1;
}

EXPORT int patch_browser_process(int pid) {
    return patch_browser_process_win((DWORD)pid);
}

#elif __APPLE__
/*
 * macOS implementation using mach_vm
 */
EXPORT int patch_browser_process(int pid) {
    task_t task;
    kern_return_t kr = task_for_pid(mach_task_self(), pid, &task);
    
    if (kr != KERN_SUCCESS) {
        fprintf(stderr, "Failed to get task for PID %d: %d\n", pid, kr);
        fprintf(stderr, "Note: Requires root privileges or taskgated entitlements\n");
        return -1;
    }
    
    printf("Got task for browser process %d\n", pid);
    
    // Enumerate memory regions
    mach_vm_address_t address = 0;
    mach_vm_size_t size = 0;
    vm_region_basic_info_data_64_t info;
    mach_msg_type_number_t info_count = VM_REGION_BASIC_INFO_COUNT_64;
    mach_port_t object_name;
    
    int patches_applied = 0;
    
    while (mach_vm_region(task, &address, &size, VM_REGION_BASIC_INFO_64,
                          (vm_region_info_t)&info, &info_count, &object_name) == KERN_SUCCESS) {
        
        // Only patch readable/writable regions
        if ((info.protection & VM_PROT_READ) && (info.protection & VM_PROT_WRITE)) {
            if (size > 1024 * 1024 * 100) {  // Skip large regions
                address += size;
                continue;
            }
            
            unsigned char* buffer = (unsigned char*)malloc(size);
            if (!buffer) {
                address += size;
                continue;
            }
            
            mach_vm_size_t bytes_read;
            kr = mach_vm_read_overwrite(task, address, size, 
                                       (mach_vm_address_t)buffer, &bytes_read);
            
            if (kr == KERN_SUCCESS) {
                // Search for automation signatures
                for (int i = 0; AUTOMATION_SIGNATURES[i] != NULL; i++) {
                    const char* sig = AUTOMATION_SIGNATURES[i];
                    size_t sig_len = strlen(sig);
                    
                    for (size_t j = 0; j < bytes_read - sig_len; j++) {
                        if (memcmp(buffer + j, sig, sig_len) == 0) {
                            printf("Found signature '%s' at offset %zu\n", sig, j);
                            
                            memset(buffer + j, 0, sig_len);
                            
                            mach_vm_write(task, address + j, 
                                        (vm_offset_t)(buffer + j), sig_len);
                            
                            patches_applied++;
                        }
                    }
                }
            }
            
            free(buffer);
        }
        
        address += size;
    }
    
    printf("Applied %d patches to browser process\n", patches_applied);
    return patches_applied > 0 ? 0 : -1;
}

#else
/*
 * Linux implementation using ptrace
 */
EXPORT int patch_browser_process(int pid) {
    printf("Linux browser patching not fully implemented (requires ptrace)\n");
    printf("Would patch PID %d\n", pid);
    
    // TODO: Full implementation using ptrace and /proc/pid/maps
    // This requires more complex memory region parsing
    
    return -1;
}
#endif


/*
 * Patch browser by executable path (find and patch all instances)
 */
EXPORT int patch_browser_by_name(const char* browser_name) {
    printf("Searching for browser processes: %s\n", browser_name);
    
    // Platform-specific process enumeration would go here
    
    return -1;
}


/*
 * Check if process is a browser
 */
EXPORT bool is_browser_process(int pid) {
    // Heuristic: check process name
    
    #ifdef _WIN32
    HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION, FALSE, pid);
    if (hProcess) {
        char path[MAX_PATH];
        if (GetModuleFileNameEx(hProcess, NULL, path, MAX_PATH)) {
            CloseHandle(hProcess);
            
            // Check for common browser names
            const char* browsers[] = {
                "chrome.exe", "firefox.exe", "msedge.exe", 
                "brave.exe", "opera.exe", NULL
            };
            
            for (int i = 0; browsers[i] != NULL; i++) {
                if (strstr(path, browsers[i])) {
                    return true;
                }
            }
        }
        CloseHandle(hProcess);
    }
    #endif
    
    return false;
}


/*
 * Get library version
 */
EXPORT const char* get_version() {
    return "1.0.0";
}


/*
 * Test function
 */
EXPORT int test_browser_patcher() {
    printf("Browser patcher loaded successfully\n");
    printf("Platform: ");
    #ifdef _WIN32
        printf("Windows\n");
    #elif __APPLE__
        printf("macOS (requires SIP disabled for injection)\n");
    #else
        printf("Linux\n");
    #endif
    
    printf("\nAutomation signatures that will be patched:\n");
    for (int i = 0; AUTOMATION_SIGNATURES[i] != NULL; i++) {
        printf("  - %s\n", AUTOMATION_SIGNATURES[i]);
    }
    
    return 0;
}
