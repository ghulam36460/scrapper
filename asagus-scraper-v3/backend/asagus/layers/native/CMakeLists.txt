cmake_minimum_required(VERSION 3.10)
project(AsagusNativeLayer VERSION 1.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_STANDARD 11)

# Output directories
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/build)

# Platform-specific settings
if(WIN32)
    set(PLATFORM_LIBS "")
    add_definitions(-D_WIN32)
elseif(APPLE)
    find_library(COCOA_LIBRARY Cocoa)
    find_library(CARBON_LIBRARY Carbon)
    find_library(APPSERVICES_LIBRARY ApplicationServices)
    set(PLATFORM_LIBS ${COCOA_LIBRARY} ${CARBON_LIBRARY} ${APPSERVICES_LIBRARY})
    add_definitions(-D__APPLE__)
else()
    # Linux
    find_package(X11 REQUIRED)
    set(PLATFORM_LIBS ${X11_LIBRARIES} ${X11_XTest_LIB})
    add_definitions(-D__linux__)
endif()

# Mouse Control Library
add_library(mouse_control SHARED src/mouse_control.cpp)
target_link_libraries(mouse_control ${PLATFORM_LIBS})
set_target_properties(mouse_control PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
    PUBLIC_HEADER ""
)

# Keyboard Control Library
add_library(keyboard_control SHARED src/keyboard_control.cpp)
target_link_libraries(keyboard_control ${PLATFORM_LIBS})
set_target_properties(keyboard_control PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
    PUBLIC_HEADER ""
)

# Browser Patcher Library
add_library(browser_patcher SHARED src/browser_patcher.c)
if(WIN32)
    target_link_libraries(browser_patcher psapi)
endif()
set_target_properties(browser_patcher PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
    PUBLIC_HEADER ""
)

# Installation rules
install(TARGETS mouse_control keyboard_control browser_patcher
    LIBRARY DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}/lib
    RUNTIME DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}/build
)

# Add compile options for optimization
if(CMAKE_BUILD_TYPE STREQUAL "Release")
    if(MSVC)
        add_compile_options(/O2 /GL)
    else()
        add_compile_options(-O3 -march=native)
    endif()
endif()

message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "Platform: ${CMAKE_SYSTEM_NAME}")
message(STATUS "C++ Compiler: ${CMAKE_CXX_COMPILER}")
message(STATUS "C Compiler: ${CMAKE_C_COMPILER}")
