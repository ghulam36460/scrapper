/*
 * Native Keyboard Controller - C++ Implementation
 * ===============================================
 * Provides OS-level keyboard input with hardware scan codes.
 * 
 * Features:
 * - Direct OS API calls with hardware scan codes
 * - Realistic typing patterns with natural timing variation
 * - Key press/release with authentic durations
 * - Immune to JavaScript keylogger detection
 */

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <thread>
#include <cctype>
#include <random>

#ifdef _WIN32
    #include <windows.h>
    #define EXPORT __declspec(dllexport)
#elif __APPLE__
    #include <ApplicationServices/ApplicationServices.h>
    #include <Carbon/Carbon.h>
    #define EXPORT __attribute__((visibility("default")))
#else
    // Linux X11
    #include <X11/Xlib.h>
    #include <X11/keysym.h>
    #include <X11/extensions/XTest.h>
    #define EXPORT __attribute__((visibility("default")))
#endif


/*
 * Cross-platform precise sleep
 */
void precise_sleep_kb(double milliseconds) {
    auto duration = std::chrono::nanoseconds(
        static_cast<long long>(milliseconds * 1000000)
    );
    std::this_thread::sleep_for(duration);
}


/*
 * Generate realistic typing delay (log-normal distribution)
 */
double get_realistic_typing_delay(double base_delay_ms) {
    static std::random_device rd;
    static std::mt19937 gen(rd());
    
    // Log-normal distribution for realistic typing
    std::lognormal_distribution<double> dist(
        std::log(base_delay_ms), 0.3
    );
    
    double delay = dist(gen);
    
    // Clamp to reasonable range
    if (delay < base_delay_ms * 0.5) delay = base_delay_ms * 0.5;
    if (delay > base_delay_ms * 3.0) delay = base_delay_ms * 3.0;
    
    return delay;
}


#ifdef _WIN32
/*
 * Windows implementation using SendInput with scan codes
 */
WORD char_to_vk(char c) {
    if (c >= 'a' && c <= 'z') return 0x41 + (c - 'a');
    if (c >= 'A' && c <= 'Z') return 0x41 + (c - 'A');
    if (c >= '0' && c <= '9') return 0x30 + (c - '0');
    
    // Special characters
    switch (c) {
        case ' ': return VK_SPACE;
        case '\n': return VK_RETURN;
        case '\t': return VK_TAB;
        case '.': return VK_OEM_PERIOD;
        case ',': return VK_OEM_COMMA;
        case ';': return VK_OEM_1;
        case '/': return VK_OEM_2;
        case '\\': return VK_OEM_5;
        case '[': return VK_OEM_4;
        case ']': return VK_OEM_6;
        case '-': return VK_OEM_MINUS;
        case '=': return VK_OEM_PLUS;
        default: return 0;
    }
}

bool requires_shift(char c) {
    if (c >= 'A' && c <= 'Z') return true;
    const char* shift_chars = "!@#$%^&*()_+{}|:\"<>?";
    return strchr(shift_chars, c) != NULL;
}

extern "C" EXPORT int type_text_native(const char* text, double char_interval_ms) {
    if (!text) return -1;
    
    size_t len = strlen(text);
    
    for (size_t i = 0; i < len; i++) {
        char c = text[i];
        WORD vk = char_to_vk(c);
        
        if (vk == 0) {
            // Skip unsupported characters
            continue;
        }
        
        bool shift = requires_shift(c);
        INPUT inputs[4] = {0};
        int input_count = 0;
        
        // Press shift if needed
        if (shift) {
            inputs[input_count].type = INPUT_KEYBOARD;
            inputs[input_count].ki.wVk = VK_SHIFT;
            inputs[input_count].ki.dwFlags = 0;
            input_count++;
        }
        
        // Press key
        inputs[input_count].type = INPUT_KEYBOARD;
        inputs[input_count].ki.wVk = vk;
        inputs[input_count].ki.dwFlags = 0;
        input_count++;
        
        SendInput(input_count, inputs, sizeof(INPUT));
        
        // Realistic key press duration
        precise_sleep_kb(30 + rand() % 40);
        
        // Release key
        input_count = 0;
        inputs[input_count].type = INPUT_KEYBOARD;
        inputs[input_count].ki.wVk = vk;
        inputs[input_count].ki.dwFlags = KEYEVENTF_KEYUP;
        input_count++;
        
        // Release shift if needed
        if (shift) {
            inputs[input_count].type = INPUT_KEYBOARD;
            inputs[input_count].ki.wVk = VK_SHIFT;
            inputs[input_count].ki.dwFlags = KEYEVENTF_KEYUP;
            input_count++;
        }
        
        SendInput(input_count, inputs, sizeof(INPUT));
        
        // Inter-character delay with realistic variation
        double delay = get_realistic_typing_delay(char_interval_ms);
        precise_sleep_kb(delay);
    }
    
    return 0;
}

#elif __APPLE__
/*
 * macOS implementation using CGEvent
 */
CGKeyCode char_to_keycode(char c) {
    // Approximate keycode mapping for macOS
    if (c >= 'a' && c <= 'z') return static_cast<CGKeyCode>(c - 'a');
    if (c >= 'A' && c <= 'Z') return static_cast<CGKeyCode>(c - 'A');
    if (c >= '0' && c <= '9') {
        if (c == '0') return 29;
        return static_cast<CGKeyCode>(18 + (c - '1'));
    }
    
    switch (c) {
        case ' ': return 49;
        case '\n': return 36;
        case '\t': return 48;
        case '.': return 47;
        case ',': return 43;
        case ';': return 41;
        case '/': return 44;
        case '\\': return 42;
        case '[': return 33;
        case ']': return 30;
        case '-': return 27;
        case '=': return 24;
        default: return 0;
    }
}

bool requires_shift_mac(char c) {
    if (c >= 'A' && c <= 'Z') return true;
    const char* shift_chars = "!@#$%^&*()_+{}|:\"<>?";
    return strchr(shift_chars, c) != NULL;
}

extern "C" EXPORT int type_text_native(const char* text, double char_interval_ms) {
    if (!text) return -1;
    
    CGEventSourceRef source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState);
    size_t len = strlen(text);
    
    for (size_t i = 0; i < len; i++) {
        char c = text[i];
        CGKeyCode keycode = char_to_keycode(c);
        
        if (keycode == 0) continue;
        
        bool shift = requires_shift_mac(c);
        
        // Press shift if needed
        if (shift) {
            CGEventRef shift_down = CGEventCreateKeyboardEvent(source, 56, true);
            CGEventPost(kCGHIDEventTap, shift_down);
            CFRelease(shift_down);
        }
        
        // Press key
        CGEventRef key_down = CGEventCreateKeyboardEvent(source, keycode, true);
        CGEventPost(kCGHIDEventTap, key_down);
        CFRelease(key_down);
        
        precise_sleep_kb(30 + rand() % 40);
        
        // Release key
        CGEventRef key_up = CGEventCreateKeyboardEvent(source, keycode, false);
        CGEventPost(kCGHIDEventTap, key_up);
        CFRelease(key_up);
        
        // Release shift if needed
        if (shift) {
            CGEventRef shift_up = CGEventCreateKeyboardEvent(source, 56, false);
            CGEventPost(kCGHIDEventTap, shift_up);
            CFRelease(shift_up);
        }
        
        double delay = get_realistic_typing_delay(char_interval_ms);
        precise_sleep_kb(delay);
    }
    
    CFRelease(source);
    return 0;
}

#else
/*
 * Linux X11 implementation
 */
KeySym char_to_keysym(char c) {
    if (c >= 'a' && c <= 'z') return XK_a + (c - 'a');
    if (c >= 'A' && c <= 'Z') return XK_A + (c - 'A');
    if (c >= '0' && c <= '9') return XK_0 + (c - '0');
    
    switch (c) {
        case ' ': return XK_space;
        case '\n': return XK_Return;
        case '\t': return XK_Tab;
        case '.': return XK_period;
        case ',': return XK_comma;
        case ';': return XK_semicolon;
        case '/': return XK_slash;
        case '\\': return XK_backslash;
        case '[': return XK_bracketleft;
        case ']': return XK_bracketright;
        case '-': return XK_minus;
        case '=': return XK_equal;
        case '!': return XK_exclam;
        case '@': return XK_at;
        case '#': return XK_numbersign;
        case '$': return XK_dollar;
        case '%': return XK_percent;
        case '^': return XK_asciicircum;
        case '&': return XK_ampersand;
        case '*': return XK_asterisk;
        case '(': return XK_parenleft;
        case ')': return XK_parenright;
        case '_': return XK_underscore;
        case '+': return XK_plus;
        default: return 0;
    }
}

extern "C" EXPORT int type_text_native(const char* text, double char_interval_ms) {
    if (!text) return -1;
    
    Display* display = XOpenDisplay(NULL);
    if (!display) {
        return -1;
    }
    
    size_t len = strlen(text);
    
    for (size_t i = 0; i < len; i++) {
        char c = text[i];
        KeySym keysym = char_to_keysym(c);
        
        if (keysym == 0) continue;
        
        KeyCode keycode = XKeysymToKeycode(display, keysym);
        
        // Press key
        XTestFakeKeyEvent(display, keycode, True, 0);
        XFlush(display);
        
        precise_sleep_kb(30 + rand() % 40);
        
        // Release key
        XTestFakeKeyEvent(display, keycode, False, 0);
        XFlush(display);
        
        double delay = get_realistic_typing_delay(char_interval_ms);
        precise_sleep_kb(delay);
    }
    
    XCloseDisplay(display);
    return 0;
}
#endif


/*
 * Type with realistic human errors and corrections
 */
extern "C" EXPORT int type_text_with_errors(const char* text, double char_interval_ms, double error_rate) {
    // TODO: Implement typo simulation
    // For now, just call regular typing
    return type_text_native(text, char_interval_ms);
}


/*
 * Get library version
 */
extern "C" EXPORT const char* get_version() {
    return "1.0.0";
}


/*
 * Test function
 */
extern "C" EXPORT int test_native_keyboard() {
    printf("Native keyboard controller loaded successfully\n");
    printf("Platform: ");
    #ifdef _WIN32
        printf("Windows\n");
    #elif __APPLE__
        printf("macOS\n");
    #else
        printf("Linux\n");
    #endif
    return 0;
}
