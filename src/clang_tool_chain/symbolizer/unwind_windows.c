/**
 * unwind_windows.c - Windows symbol resolution for libunwind
 *
 * This file implements symbol resolution for libunwind on Windows using
 * COFF symbol table parsing for MinGW executables.
 *
 * The MinGW libunwind library does not implement unw_get_proc_name(),
 * returning UNW_ENOINFO (-6549). This implementation provides working
 * symbol resolution by reading the COFF symbol table embedded in the PE
 * executable.
 *
 * Compile: clang-tool-chain-c unwind_windows.c -c -o unwind_windows.o
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (c) 2026 clang-tool-chain contributors
 */

#ifdef _WIN32

#include "unwind_windows.h"

#include <windows.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* Thread-safe initialization flag */
static volatile LONG g_initialized = 0;
static CRITICAL_SECTION g_sym_lock;
static volatile LONG g_lock_initialized = 0;

/* Symbol table structure */
typedef struct {
    DWORD64 address;
    char name[256];
} symbol_entry_t;

/* Global symbol table (sorted by address for binary search) */
static symbol_entry_t *g_symbol_table = NULL;
static size_t g_symbol_count = 0;
static DWORD64 g_image_base = 0;
static DWORD64 g_runtime_base = 0;

/* Initialize the critical section for thread safety */
static void init_lock(void) {
    if (InterlockedCompareExchange(&g_lock_initialized, 1, 0) == 0) {
        InitializeCriticalSection(&g_sym_lock);
    }
}

/* COFF symbol table entry (18 bytes) */
#pragma pack(push, 1)
typedef struct {
    union {
        char ShortName[8];
        struct {
            DWORD Zeros;
            DWORD Offset;
        } LongName;
    } Name;
    DWORD Value;
    SHORT SectionNumber;
    WORD Type;
    BYTE StorageClass;
    BYTE NumberOfAuxSymbols;
} COFF_SYMBOL;
#pragma pack(pop)

/* Comparison function for qsort */
static int compare_symbols(const void *a, const void *b) {
    const symbol_entry_t *sa = (const symbol_entry_t *)a;
    const symbol_entry_t *sb = (const symbol_entry_t *)b;
    if (sa->address < sb->address) return -1;
    if (sa->address > sb->address) return 1;
    return 0;
}

/* Check if section is executable */
static BOOL is_executable_section(IMAGE_SECTION_HEADER *section) {
    return (section->Characteristics & IMAGE_SCN_CNT_CODE) != 0 ||
           (section->Characteristics & IMAGE_SCN_MEM_EXECUTE) != 0;
}

/* Check if this is a text symbol (function) */
static BOOL is_text_symbol(COFF_SYMBOL *sym, IMAGE_SECTION_HEADER *sections, WORD num_sections) {
    /* Must have a valid section number */
    if (sym->SectionNumber <= 0 || sym->SectionNumber > num_sections) {
        return FALSE;
    }

    /* Check if symbol is in an executable section */
    IMAGE_SECTION_HEADER *section = &sections[sym->SectionNumber - 1];
    if (!is_executable_section(section)) {
        return FALSE;
    }

    /* Check storage class and type */
    BYTE storage = sym->StorageClass;
    WORD derived_type = (sym->Type >> 4) & 0x3;

    /* Function type in COFF is 0x20 (function derived type) */
    if (derived_type == 2) {  /* IMAGE_SYM_DTYPE_FUNCTION */
        return TRUE;
    }

    /* External or static symbols in code sections are likely functions */
    if (storage == 2 || storage == 3) {  /* EXTERNAL or STATIC */
        return TRUE;
    }

    return FALSE;
}

/* Parse COFF symbol table from the current executable */
static int parse_coff_symbols(void) {
    char exe_path[MAX_PATH];
    DWORD path_len = GetModuleFileNameA(NULL, exe_path, MAX_PATH);
    if (path_len == 0 || path_len >= MAX_PATH) {
        return -1;
    }

    /* Get runtime base address */
    HMODULE exe_module = GetModuleHandleA(NULL);
    g_runtime_base = (DWORD64)exe_module;

    /* Open the executable file */
    HANDLE file = CreateFileA(exe_path, GENERIC_READ, FILE_SHARE_READ,
                               NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return -1;
    }

    /* Map the file into memory */
    HANDLE mapping = CreateFileMappingA(file, NULL, PAGE_READONLY, 0, 0, NULL);
    if (mapping == NULL) {
        CloseHandle(file);
        return -1;
    }

    LPVOID base = MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, 0);
    if (base == NULL) {
        CloseHandle(mapping);
        CloseHandle(file);
        return -1;
    }

    /* Parse PE header */
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        UnmapViewOfFile(base);
        CloseHandle(mapping);
        CloseHandle(file);
        return -1;
    }

    IMAGE_NT_HEADERS64 *nt = (IMAGE_NT_HEADERS64 *)((BYTE *)base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) {
        UnmapViewOfFile(base);
        CloseHandle(mapping);
        CloseHandle(file);
        return -1;
    }

    /* Get image base for address calculation */
    g_image_base = nt->OptionalHeader.ImageBase;

    /* Get COFF symbol table info */
    DWORD symbol_table_offset = nt->FileHeader.PointerToSymbolTable;
    DWORD symbol_count = nt->FileHeader.NumberOfSymbols;

    if (symbol_table_offset == 0 || symbol_count == 0) {
        /* No COFF symbols - this is normal for release builds */
        UnmapViewOfFile(base);
        CloseHandle(mapping);
        CloseHandle(file);
        return 0;
    }

    /* Get section headers for address calculation */
    IMAGE_SECTION_HEADER *sections = (IMAGE_SECTION_HEADER *)((BYTE *)&nt->OptionalHeader +
                                                                nt->FileHeader.SizeOfOptionalHeader);
    WORD num_sections = nt->FileHeader.NumberOfSections;

    /* Get pointer to COFF symbol table */
    COFF_SYMBOL *symbols = (COFF_SYMBOL *)((BYTE *)base + symbol_table_offset);

    /* String table immediately follows symbol table */
    char *string_table = (char *)((BYTE *)symbols + symbol_count * sizeof(COFF_SYMBOL));

    /* Count text symbols first */
    size_t func_count = 0;
    for (DWORD i = 0; i < symbol_count; i++) {
        COFF_SYMBOL *sym = &symbols[i];

        if (is_text_symbol(sym, sections, num_sections)) {
            func_count++;
        }

        i += sym->NumberOfAuxSymbols;
    }

    if (func_count == 0) {
        UnmapViewOfFile(base);
        CloseHandle(mapping);
        CloseHandle(file);
        return 0;
    }

    /* Allocate symbol table */
    g_symbol_table = (symbol_entry_t *)malloc(func_count * sizeof(symbol_entry_t));
    if (!g_symbol_table) {
        UnmapViewOfFile(base);
        CloseHandle(mapping);
        CloseHandle(file);
        return -1;
    }

    /* Fill symbol table */
    size_t idx = 0;
    for (DWORD i = 0; i < symbol_count && idx < func_count; i++) {
        COFF_SYMBOL *sym = &symbols[i];

        if (!is_text_symbol(sym, sections, num_sections)) {
            i += sym->NumberOfAuxSymbols;
            continue;
        }

        /* Get symbol name */
        char name[256];
        if (sym->Name.LongName.Zeros == 0) {
            /* Long name - offset into string table */
            strncpy(name, string_table + sym->Name.LongName.Offset, 255);
            name[255] = '\0';
        } else {
            /* Short name - directly in entry */
            memcpy(name, sym->Name.ShortName, 8);
            name[8] = '\0';
        }

        /* Skip internal symbols */
        if (name[0] == '.') {
            i += sym->NumberOfAuxSymbols;
            continue;
        }

        /* Calculate virtual address (relative to image base) */
        WORD section_idx = sym->SectionNumber - 1;
        DWORD64 rva = sections[section_idx].VirtualAddress + sym->Value;

        /* Store runtime address (with ASLR) */
        g_symbol_table[idx].address = g_runtime_base + rva;
        strncpy(g_symbol_table[idx].name, name, 255);
        g_symbol_table[idx].name[255] = '\0';
        idx++;

        i += sym->NumberOfAuxSymbols;
    }

    g_symbol_count = idx;

    /* Sort by address for binary search */
    qsort(g_symbol_table, g_symbol_count, sizeof(symbol_entry_t), compare_symbols);

    UnmapViewOfFile(base);
    CloseHandle(mapping);
    CloseHandle(file);

    return 0;
}

/* Ensure symbols are loaded */
static int ensure_initialized(void) {
    init_lock();

    if (g_initialized) {
        return 0;
    }

    EnterCriticalSection(&g_sym_lock);

    if (g_initialized) {
        LeaveCriticalSection(&g_sym_lock);
        return 0;
    }

    int result = parse_coff_symbols();
    g_initialized = 1;

    LeaveCriticalSection(&g_sym_lock);
    return result;
}

int unw_windows_sym_init(void) {
    return ensure_initialized();
}

void unw_windows_sym_cleanup(void) {
    if (g_initialized) {
        EnterCriticalSection(&g_sym_lock);
        if (g_initialized) {
            if (g_symbol_table) {
                free(g_symbol_table);
                g_symbol_table = NULL;
            }
            g_symbol_count = 0;
            g_initialized = 0;
        }
        LeaveCriticalSection(&g_sym_lock);
    }
}

/* Find symbol by address using binary search */
static symbol_entry_t *find_symbol(DWORD64 address) {
    if (!g_symbol_table || g_symbol_count == 0) {
        return NULL;
    }

    /* Binary search for the largest address <= target */
    size_t low = 0;
    size_t high = g_symbol_count;
    symbol_entry_t *best = NULL;

    while (low < high) {
        size_t mid = low + (high - low) / 2;
        if (g_symbol_table[mid].address <= address) {
            best = &g_symbol_table[mid];
            low = mid + 1;
        } else {
            high = mid;
        }
    }

    /* Validate that the symbol is reasonable (offset < 1MB) */
    if (best && (address - best->address) < 0x100000) {
        return best;
    }

    return NULL;
}

int unw_get_proc_name_windows(unw_cursor_t *cursor, char *buf, size_t buf_len,
                               unw_word_t *offp) {
    if (!cursor || !buf || buf_len == 0) {
        return UNW_EUNSPEC;
    }

    /* Initialize symbol table if not already done */
    if (ensure_initialized() != 0) {
        return UNW_EUNSPEC;
    }

    /* Get instruction pointer from cursor */
    unw_word_t ip = 0;
    if (unw_get_reg(cursor, UNW_REG_IP, &ip) != 0) {
        return UNW_EUNSPEC;
    }

    if (ip == 0) {
        return UNW_ENOINFO;
    }

    /* Find symbol containing this address */
    symbol_entry_t *sym = find_symbol((DWORD64)ip);
    if (!sym) {
        return UNW_ENOINFO;
    }

    /* Copy symbol name to output buffer */
    size_t name_len = strlen(sym->name);
    if (name_len >= buf_len) {
        name_len = buf_len - 1;
    }
    memcpy(buf, sym->name, name_len);
    buf[name_len] = '\0';

    /* Set offset if requested */
    if (offp) {
        *offp = (unw_word_t)(ip - sym->address);
    }

    return 0;
}

/**
 * _Ux86_64_get_proc_name - Internal libunwind function for symbol resolution
 *
 * This is the internal function that MinGW libunwind calls from unw_get_proc_name().
 * By providing this implementation, we make libunwind's symbol resolution work on Windows.
 *
 * The MinGW libunwind declares this as a weak symbol that returns UNW_ENOINFO.
 * By linking with this library (or compiling this file with your program),
 * our implementation takes precedence and provides actual symbol resolution
 * using the COFF symbol table embedded in the PE executable.
 *
 * Usage:
 *   Option 1: Link the pre-built DLL:
 *     clang-tool-chain-c your_program.c -lunwind -lunwind_proc_name -o program.exe
 *
 *   Option 2: Compile this file with your program:
 *     clang-tool-chain-c unwind_windows.c your_program.c -lunwind -o program.exe
 *
 * After linking, unw_get_proc_name() will return function names instead of UNW_ENOINFO.
 */
int _Ux86_64_get_proc_name(unw_cursor_t *cursor, char *buf, size_t buf_len,
                            unw_word_t *offp) {
    return unw_get_proc_name_windows(cursor, buf, buf_len, offp);
}

/**
 * __wrap__Ux86_64_get_proc_name - For use with -Wl,--wrap linker option
 *
 * This provides an alternative linking method using --wrap:
 *   clang-tool-chain-c your_program.c -lunwind -Wl,--wrap=_Ux86_64_get_proc_name -o program.exe
 *
 * When using --wrap, the linker redirects calls to _Ux86_64_get_proc_name
 * to __wrap__Ux86_64_get_proc_name.
 */
int __wrap__Ux86_64_get_proc_name(unw_cursor_t *cursor, char *buf, size_t buf_len,
                                   unw_word_t *offp) {
    return unw_get_proc_name_windows(cursor, buf, buf_len, offp);
}

/**
 * Override functions for LLVM libunwind.
 *
 * These are defined when compiling directly (not as shared library).
 * They override the LLVM libunwind functions to use our implementation.
 *
 * When building as shared library (-DBUILDING_DLL), these are not defined
 * to avoid duplicate symbol errors with libunwind.a.
 */
#ifndef BUILDING_DLL

/**
 * __unw_get_proc_name - LLVM libunwind internal function
 *
 * This provides the LLVM libunwind internal function that unw_get_proc_name() aliases to.
 * When this file is linked BEFORE libunwind.a, this definition takes precedence.
 *
 * IMPORTANT: Link order matters! This file must be linked BEFORE -lunwind:
 *   clang-tool-chain-c unwind_windows.c your_program.c -lunwind -o program.exe
 */
int __unw_get_proc_name(unw_cursor_t *cursor, char *buf, size_t buf_len,
                         unw_word_t *offp) {
    return unw_get_proc_name_windows(cursor, buf, buf_len, offp);
}

/**
 * unw_get_proc_name - Standard libunwind API function
 *
 * This directly provides the user-facing API function.
 * When this file is linked BEFORE libunwind.a, this definition takes precedence.
 */
int unw_get_proc_name(unw_cursor_t *cursor, char *buf, size_t buf_len,
                       unw_word_t *offp) {
    return unw_get_proc_name_windows(cursor, buf, buf_len, offp);
}

#endif /* BUILDING_DLL */

#endif /* _WIN32 */
