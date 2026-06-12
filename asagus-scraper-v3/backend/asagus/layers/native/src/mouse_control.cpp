/*
 * Native Mouse Controller - C++ Implementation
 * ===========================================
 * Provides OS-level mouse control that bypasses JavaScript detection.
 * 
 * Features:
 * - Direct OS API calls (Windows: SendInput, Linux: X11/Wayland, macOS: CGEvent)
 * - Hardware-accurate timing with nanosecond precision
 * - Realistic Bezier curve movements
 * - Immune to JavaScript event listener detection
 */

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <thread>
#include <vector>

#ifdef _WIN32
    #include <windows.h>
    #define EXPORT __declspec(dllexport)
#elif __APPLE__
    #include <ApplicationServices/ApplicationServices.h>
    #define EXPORT __attribute__((visibility("default")))
#else
    // Linux X11
    #include <X11/Xlib.h>
    #include <X11/extensions/XTest.h>
    #define EXPORT __attribute__((visibility("default")))
#endif


/*
 * Cross-platform sleep with nanosecond precision
 */
void precise_sleep(double milliseconds) {
    auto duration = std::chrono::nanoseconds(
        static_cast<long long>(milliseconds * 1000000)
    );
    std::this_thread::sleep_for(duration);
}


/*
 * Generate Bezier curve points for realistic mouse movement
 */
std::vector<std::pair<int, int>> generate_bezier_path(
    int x_start, int y_start,
    int x_end, int y_end,
    int num_points
) {
    std::vector<std::pair<int, int>> path;
    
    // Control points for cubic Bezier
    int cx1 = x_start + (x_end - x_start) / 3 + (rand() % 100 - 50);
    int cy1 = y_start + (y_end - y_start) / 3 + (rand() % 100 - 50);
    int cx2 = x_start + 2 * (x_end - x_start) / 3 + (rand() % 100 - 50);
    int cy2 = y_start + 2 * (y_end - y_start) / 3 + (rand() % 100 - 50);
    
    for (int i = 0; i <= num_points; i++) {
        double t = static_cast<double>(i) / num_points;
        double t2 = t * t;
        double t3 = t2 * t;
        double mt = 1 - t;
        double mt2 = mt * mt;
        double mt3 = mt2 * mt;
        
        // Cubic Bezier formula
        int x = static_cast<int>(
            mt3 * x_start +
            3 * mt2 * t * cx1 +
            3 * mt * t2 * cx2 +
            t3 * x_end
        );
        
        int y = static_cast<int>(
            mt3 * y_start +
            3 * mt2 * t * cy1 +
            3 * mt * t2 * cy2 +
            t3 * y_end
        );
        
        path.push_back({x, y});
    }
    
    return path;
}


#ifdef _WIN32
/*
 * Windows implementation using SendInput
 */
extern "C" EXPORT int move_mouse_native(int x, int y, double duration_ms) {
    POINT current_pos;
    if (!GetCursorPos(&current_pos)) {
        return -1;
    }
    
    int num_steps = static_cast<int>(duration_ms / 10);  // 10ms per step
    if (num_steps < 5) num_steps = 5;
    
    auto path = generate_bezier_path(current_pos.x, current_pos.y, x, y, num_steps);
    double step_delay = duration_ms / num_steps;
    
    for (const auto& point : path) {
        // Absolute screen coordinates
        int abs_x = point.first * 65536 / GetSystemMetrics(SM_CXSCREEN);
        int abs_y = point.second * 65536 / GetSystemMetrics(SM_CYSCREEN);
        
        INPUT input = {0};
        input.type = INPUT_MOUSE;
        input.mi.dx = abs_x;
        input.mi.dy = abs_y;
        input.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE;
        
        SendInput(1, &input, sizeof(INPUT));
        precise_sleep(step_delay);
    }
    
    return 0;
}

extern "C" EXPORT int click_mouse_native(int button, int x, int y) {
    // Move to position first
    int abs_x = x * 65536 / GetSystemMetrics(SM_CXSCREEN);
    int abs_y = y * 65536 / GetSystemMetrics(SM_CYSCREEN);
    
    INPUT inputs[2] = {0};
    
    // Mouse down
    inputs[0].type = INPUT_MOUSE;
    inputs[0].mi.dx = abs_x;
    inputs[0].mi.dy = abs_y;
    inputs[0].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE;
    
    if (button == 0) {  // Left button
        inputs[0].mi.dwFlags |= MOUSEEVENTF_LEFTDOWN;
        inputs[1].mi.dwFlags = MOUSEEVENTF_LEFTUP;
    } else if (button == 1) {  // Right button
        inputs[0].mi.dwFlags |= MOUSEEVENTF_RIGHTDOWN;
        inputs[1].mi.dwFlags = MOUSEEVENTF_RIGHTUP;
    } else {  // Middle button
        inputs[0].mi.dwFlags |= MOUSEEVENTF_MIDDLEDOWN;
        inputs[1].mi.dwFlags = MOUSEEVENTF_MIDDLEUP;
    }
    
    inputs[1].type = INPUT_MOUSE;
    
    SendInput(1, &inputs[0], sizeof(INPUT));
    precise_sleep(50 + rand() % 50);  // Realistic click duration
    SendInput(1, &inputs[1], sizeof(INPUT));
    
    return 0;
}

#elif __APPLE__
/*
 * macOS implementation using CGEvent
 */
extern "C" EXPORT int move_mouse_native(int x, int y, double duration_ms) {
    CGEventRef event = CGEventCreate(NULL);
    CGPoint current_pos = CGEventGetLocation(event);
    CFRelease(event);
    
    int num_steps = static_cast<int>(duration_ms / 10);
    if (num_steps < 5) num_steps = 5;
    
    auto path = generate_bezier_path(
        static_cast<int>(current_pos.x),
        static_cast<int>(current_pos.y),
        x, y, num_steps
    );
    double step_delay = duration_ms / num_steps;
    
    for (const auto& point : path) {
        CGPoint new_pos = CGPointMake(point.first, point.second);
        CGEventRef move = CGEventCreateMouseEvent(
            NULL, kCGEventMouseMoved,
            new_pos, kCGMouseButtonLeft
        );
        CGEventPost(kCGHIDEventTap, move);
        CFRelease(move);
        
        precise_sleep(step_delay);
    }
    
    return 0;
}

extern "C" EXPORT int click_mouse_native(int button, int x, int y) {
    CGPoint pos = CGPointMake(x, y);
    
    CGEventType down_type, up_type;
    CGMouseButton mouse_button;
    
    if (button == 0) {  // Left
        down_type = kCGEventLeftMouseDown;
        up_type = kCGEventLeftMouseUp;
        mouse_button = kCGMouseButtonLeft;
    } else if (button == 1) {  // Right
        down_type = kCGEventRightMouseDown;
        up_type = kCGEventRightMouseUp;
        mouse_button = kCGMouseButtonRight;
    } else {  // Middle
        down_type = kCGEventOtherMouseDown;
        up_type = kCGEventOtherMouseUp;
        mouse_button = kCGMouseButtonCenter;
    }
    
    CGEventRef down = CGEventCreateMouseEvent(NULL, down_type, pos, mouse_button);
    CGEventRef up = CGEventCreateMouseEvent(NULL, up_type, pos, mouse_button);
    
    CGEventPost(kCGHIDEventTap, down);
    precise_sleep(50 + rand() % 50);
    CGEventPost(kCGHIDEventTap, up);
    
    CFRelease(down);
    CFRelease(up);
    
    return 0;
}

#else
/*
 * Linux X11 implementation
 */
extern "C" EXPORT int move_mouse_native(int x, int y, double duration_ms) {
    Display* display = XOpenDisplay(NULL);
    if (!display) {
        return -1;
    }
    
    Window root = DefaultRootWindow(display);
    int current_x, current_y;
    Window root_ret, child_ret;
    int win_x, win_y;
    unsigned int mask;
    
    XQueryPointer(display, root, &root_ret, &child_ret,
                  &current_x, &current_y, &win_x, &win_y, &mask);
    
    int num_steps = static_cast<int>(duration_ms / 10);
    if (num_steps < 5) num_steps = 5;
    
    auto path = generate_bezier_path(current_x, current_y, x, y, num_steps);
    double step_delay = duration_ms / num_steps;
    
    for (const auto& point : path) {
        XTestFakeMotionEvent(display, -1, point.first, point.second, 0);
        XFlush(display);
        precise_sleep(step_delay);
    }
    
    XCloseDisplay(display);
    return 0;
}

extern "C" EXPORT int click_mouse_native(int button, int x, int y) {
    Display* display = XOpenDisplay(NULL);
    if (!display) {
        return -1;
    }
    
    // Move first
    XTestFakeMotionEvent(display, -1, x, y, 0);
    XFlush(display);
    
    // Click (button 1=left, 2=middle, 3=right in X11)
    int x11_button = button == 1 ? 3 : (button == 2 ? 2 : 1);
    
    XTestFakeButtonEvent(display, x11_button, True, 0);
    XFlush(display);
    
    precise_sleep(50 + rand() % 50);
    
    XTestFakeButtonEvent(display, x11_button, False, 0);
    XFlush(display);
    
    XCloseDisplay(display);
    return 0;
}
#endif


/*
 * Get library version
 */
extern "C" EXPORT const char* get_version() {
    return "1.0.0";
}


/*
 * Test function
 */
extern "C" EXPORT int test_native_mouse() {
    printf("Native mouse controller loaded successfully\n");
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
