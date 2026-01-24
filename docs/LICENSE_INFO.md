# License Information

License details for clang-tool-chain and bundled components.

## clang-tool-chain Package License

**License:** Apache License 2.0

**Copyright:** Copyright (c) Zachary Vorhies and contributors

**Full License Text:** See [LICENSE](../LICENSE) file in the repository root.

### Summary

The clang-tool-chain Python package (wrapper code, installers, utilities) is licensed under Apache 2.0:

- ✅ **Commercial use** allowed
- ✅ **Modification** allowed
- ✅ **Distribution** allowed
- ✅ **Patent grant** included
- ⚠️ **Warranty** NOT PROVIDED ("as is")
- ⚠️ **Liability** LIMITED (see license)

### Key Points

- You can use clang-tool-chain in commercial projects
- You can modify and distribute your modified versions
- You must include the Apache 2.0 license notice
- You must include a NOTICE file if one is provided
- Changes must be documented

## Bundled Clang/LLVM Binaries License

**License:** Apache License 2.0 with LLVM Exception

**Copyright:** Copyright (c) LLVM Project contributors

**Full License Text:** https://llvm.org/LICENSE.txt

### Summary

The Clang/LLVM binaries distributed by clang-tool-chain are licensed under Apache 2.0 with LLVM Exception:

- ✅ **Commercial use** allowed
- ✅ **Modification** allowed
- ✅ **Distribution** allowed
- ✅ **Patent grant** included
- ✅ **LLVM Exception** - More permissive than plain Apache 2.0

### LLVM Exception

The LLVM Exception provides additional permissions:

> As an exception, if, as a result of your compiling your source code, portions
> of this Software are embedded into an Object form of such source code, you
> may redistribute such embedded portions in such Object form without complying
> with the conditions of Sections 4(a), 4(b) and 4(d) of the License.

**Practical meaning:** Binaries you compile with Clang don't need to include LLVM license notices.

### Key Points

- You can use LLVM in commercial projects
- Binaries you compile with Clang are yours (no license obligations)
- Redistribution of LLVM itself requires Apache 2.0 compliance
- Patent grant protects you from LLVM contributors' patents

## Emscripten SDK License

**License:** MIT License and University of Illinois/NCSA Open Source License

**Copyright:** Copyright (c) Emscripten authors

**Full License Text:** https://github.com/emscripten-core/emscripten/blob/main/LICENSE

### Summary

Emscripten SDK uses dual licensing:

- **MIT License** - Emscripten tools and scripts
- **UIUC/NCSA License** - LLVM components (similar to Apache 2.0)

Both licenses are highly permissive:
- ✅ **Commercial use** allowed
- ✅ **Modification** allowed
- ✅ **Distribution** allowed
- ⚠️ **Warranty** NOT PROVIDED

### Key Points

- You can use Emscripten in commercial projects
- WebAssembly binaries you create are yours (no license obligations)
- Redistribution of Emscripten SDK requires license notices

## Node.js Runtime License

**License:** MIT License

**Copyright:** Copyright (c) Node.js contributors

**Full License Text:** https://github.com/nodejs/node/blob/main/LICENSE

### Summary

Node.js bundled with clang-tool-chain uses the MIT License:

- ✅ **Commercial use** allowed
- ✅ **Modification** allowed
- ✅ **Distribution** allowed
- ⚠️ **Warranty** NOT PROVIDED

### Key Points

- You can use bundled Node.js in commercial projects
- No restrictions on applications you run with Node.js

## Include What You Use (IWYU) License

**License:** University of Illinois/NCSA Open Source License

**Copyright:** Copyright (c) IWYU contributors

**Full License Text:** https://github.com/include-what-you-use/include-what-you-use/blob/master/LICENSE.TXT

### Summary

IWYU uses the UIUC/NCSA License (similar to MIT/BSD):

- ✅ **Commercial use** allowed
- ✅ **Modification** allowed
- ✅ **Distribution** allowed
- ⚠️ **Warranty** NOT PROVIDED

### Key Points

- You can use IWYU in commercial projects
- Code you analyze with IWYU has no license obligations

## LLDB Debugger License

**License:** Apache License 2.0 with LLVM Exception

**Copyright:** Copyright (c) LLVM Project contributors

**Full License Text:** https://llvm.org/LICENSE.txt

### Summary

LLDB uses the same license as LLVM (Apache 2.0 with LLVM Exception):

- ✅ **Commercial use** allowed
- ✅ **Modification** allowed
- ✅ **Distribution** allowed
- ✅ **Patent grant** included

### Key Points

- You can use LLDB in commercial projects
- Programs you debug with LLDB have no license obligations

## Cosmopolitan Libc License

**License:** ISC License (similar to MIT/BSD)

**Copyright:** Copyright (c) Justine Tunney and Cosmopolitan contributors

**Full License Text:** https://github.com/jart/cosmopolitan/blob/master/LICENSE

### Summary

Cosmopolitan Libc uses the ISC License (extremely permissive):

- ✅ **Commercial use** allowed
- ✅ **Modification** allowed
- ✅ **Distribution** allowed
- ⚠️ **Warranty** NOT PROVIDED

### Key Points

- You can use Cosmopolitan in commercial projects
- Actually Portable Executables you create are yours
- Static linking allowed without license obligations

## MinGW-w64 License (Windows Only)

**License:** Multiple licenses (ZPL, BSD, MIT)

**Copyright:** Copyright (c) MinGW-w64 contributors

**Full License Text:** https://sourceforge.net/p/mingw-w64/mingw-w64/ci/master/tree/COPYING

### Summary

MinGW-w64 runtime libraries use permissive licenses:

- **Runtime libraries** - Public domain or ZPL (no restrictions)
- **Headers** - BSD/MIT licenses
- **Tools** - GPL (not distributed with clang-tool-chain)

### Key Points

- You can use MinGW runtime in commercial projects
- Executables you create have no license obligations
- MinGW DLLs can be redistributed freely

## Python Dependencies

clang-tool-chain uses Python libraries with permissive licenses:

| Dependency | License | Commercial Use |
|------------|---------|----------------|
| **pyzstd** | BSD 3-Clause | ✅ Allowed |
| **fasteners** | Apache 2.0 | ✅ Allowed |
| **requests** | Apache 2.0 | ✅ Allowed |
| **tqdm** | MPL 2.0 / MIT | ✅ Allowed |
| **setenvironment** | MIT | ✅ Allowed |
| **sccache** (optional) | Apache 2.0 | ✅ Allowed |

All dependencies allow commercial use, modification, and distribution.

## License Compliance Checklist

When using clang-tool-chain in a project:

### ✅ You Can:
- Use in commercial projects
- Compile proprietary software
- Distribute executables without license notices
- Modify clang-tool-chain and distribute your version
- Use in closed-source projects

### ⚠️ You Must:
- Include Apache 2.0 license if redistributing clang-tool-chain package
- Include LLVM license if redistributing LLVM binaries
- Document modifications if distributing modified versions
- Include copyright notices in redistributions

### ❌ You Cannot:
- Hold authors liable for damages
- Claim warranty or guarantees
- Use trademarks without permission

## Compiled Binary Licensing

**Programs you compile with clang-tool-chain:**

Your compiled binaries are **yours**. You can:
- License them however you want (MIT, GPL, proprietary, etc.)
- Distribute them commercially
- Keep them closed-source
- Not include any LLVM or clang-tool-chain licenses

**Exception:** If you statically link GPLed libraries, the GPL applies to the combined work.

## Redistributing clang-tool-chain

If you want to redistribute clang-tool-chain itself (not just use it):

**Requirements:**
1. Include Apache 2.0 license notice
2. Include LLVM license for bundled binaries
3. Document any modifications
4. Include NOTICE file if provided

**Example redistribution scenarios:**
- Forking clang-tool-chain on GitHub
- Creating a derived package
- Bundling with a commercial IDE

## Attribution

When redistributing clang-tool-chain binaries, include:

```
This software includes components from:
- LLVM Project (https://llvm.org/) - Apache 2.0 with LLVM Exception
- Emscripten (https://emscripten.org/) - MIT License
- MinGW-w64 (https://mingw-w64.org/) - ZPL/BSD/MIT Licenses
- Cosmopolitan Libc (https://justine.lol/cosmopolitan/) - ISC License
```

## Warranty Disclaimer

**clang-tool-chain is provided "AS IS"**, without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement.

**In no event shall the authors or copyright holders be liable** for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

## Questions?

For licensing questions:
- **clang-tool-chain package:** [GitHub Issues](https://github.com/zackees/clang-tool-chain/issues)
- **LLVM/Clang:** [LLVM License](https://llvm.org/LICENSE.txt)
- **Emscripten:** [Emscripten License](https://github.com/emscripten-core/emscripten/blob/main/LICENSE)
- **Legal advice:** Consult a lawyer (this is not legal advice)

## Further Reading

- [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)
- [LLVM License (Apache 2.0 with LLVM Exception)](https://llvm.org/LICENSE.txt)
- [MIT License](https://opensource.org/licenses/MIT)
- [ISC License](https://opensource.org/licenses/ISC)
- [Open Source Initiative](https://opensource.org/)

---

**Summary:** All components use permissive licenses that allow commercial use, modification, and distribution. Binaries you compile are yours with no license obligations.
