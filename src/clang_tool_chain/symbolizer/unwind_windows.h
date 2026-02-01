/**
 * unwind_windows.h - Windows symbol resolution for libunwind
 *
 * This header provides symbol resolution for libunwind on Windows.
 * MinGW libunwind does not implement symbol resolution, returning UNW_ENOINFO.
 * This implementation reads the COFF symbol table embedded in the PE
 * executable for symbol resolution.
 *
 * AUTOMATIC INTEGRATION:
 *   When you link with this library, the internal _Ux86_64_get_proc_name()
 *   function is provided, making libunwind's unw_get_proc_name() work
 *   automatically. No code changes needed!
 *
 *   Example:
 *     clang-tool-chain-c your_program.c -lunwind -lunwind_proc_name -o program.exe
 *
 *   Or compile unwind_windows.c directly:
 *     clang-tool-chain-c unwind_windows.c your_program.c -lunwind -o program.exe
 *
 * MANUAL USAGE (alternative):
 *   #ifdef _WIN32
 *   #include <unwind_windows.h>
 *   #define unw_get_proc_name unw_get_proc_name_windows
 *   #endif
 *
 * No additional libraries required for linking (uses Windows API only).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (c) 2026 clang-tool-chain contributors
 */

#ifndef UNWIND_WINDOWS_H
#define UNWIND_WINDOWS_H

#ifdef _WIN32

#include <libunwind.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Resolve function name for the current cursor position.
 *
 * This is a Windows-specific replacement for unw_get_proc_name() that uses
 * DbgHelp for symbol resolution instead of returning UNW_ENOINFO.
 *
 * @param cursor    libunwind cursor pointing to a stack frame
 * @param buf       Buffer to store the function name
 * @param buf_len   Size of the buffer
 * @param offp      Pointer to store the offset from function start (can be NULL)
 *
 * @return 0 on success, UNW_ENOINFO if symbol not found, UNW_EUNSPEC on error
 */
int unw_get_proc_name_windows(unw_cursor_t *cursor, char *buf, size_t buf_len,
                               unw_word_t *offp);

/**
 * Initialize Windows symbol resolution.
 *
 * This function initializes the DbgHelp library for the current process.
 * It is called automatically by unw_get_proc_name_windows() on first use,
 * but can be called explicitly for earlier initialization.
 *
 * @return 0 on success, non-zero on error
 */
int unw_windows_sym_init(void);

/**
 * Cleanup Windows symbol resolution.
 *
 * Call this before program exit to free DbgHelp resources.
 * Optional but recommended for clean shutdown.
 */
void unw_windows_sym_cleanup(void);

/**
 * Internal libunwind function for symbol resolution (nongnu libunwind).
 *
 * This function provides the internal implementation for nongnu libunwind.
 * The MinGW libunwind declares this as a weak symbol that returns UNW_ENOINFO.
 * Our implementation overrides the weak symbol and provides actual symbol
 * resolution using the COFF symbol table.
 *
 * @param cursor    libunwind cursor pointing to a stack frame
 * @param buf       Buffer to store the function name
 * @param buf_len   Size of the buffer
 * @param offp      Pointer to store the offset from function start (can be NULL)
 *
 * @return 0 on success, UNW_ENOINFO if symbol not found, UNW_EUNSPEC on error
 */
int _Ux86_64_get_proc_name(unw_cursor_t *cursor, char *buf, size_t buf_len,
                            unw_word_t *offp);

/*
 * The following functions override LLVM libunwind functions.
 * They are only defined when compiling unwind_windows.c directly with your
 * program (not when building as a DLL).
 *
 * Compile order: unwind_windows.c must come BEFORE -lunwind in the command:
 *   clang-tool-chain-c unwind_windows.c your_program.c -lunwind -o program.exe
 */

#ifdef __cplusplus
}
#endif

#endif /* _WIN32 */

#endif /* UNWIND_WINDOWS_H */
