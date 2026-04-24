# Upstream issue to file on zackees/zccache

Paste the block below at https://github.com/zackees/zccache/issues/new.

---

**Title:** Stability commitments needed for downstream adoption (clang-tool-chain)

**Body:**

Hi — adopting zccache as a hard dep in
[`clang-tool-chain`](https://github.com/zackees/clang-tool-chain) to
replace our custom Rust launcher + sccache integration. Before we cut
that over, we need to align on a few API commitments since our README
currently labels zccache *"Early development — architecture and
scaffolding phase"*.

Three asks, in priority order:

### 1. Tag a GitHub release for 1.2.12

`Cargo.toml` says `1.2.12` but the latest GH tag is `1.2.8` (2026-04-13).
PyPI wheel 1.2.12 is live. We want to pin `zccache==1.2.12` in our
pyproject and be able to point at a tag from release notes. A one-line
commit-and-push.

### 2. Freeze the `ZCCACHE_LINK_DEPLOY_CMD` contract

Added 2026-04-18 in `crates/zccache-daemon/src/server.rs:1658`. We wire
our post-link DLL/dylib deployer through this hook. Please don't change:

- Hook-invocation semantics: fires **only on cache-miss links**,
  command-line is `"$ZCCACHE_LINK_DEPLOY_CMD" <output_path>`, hook
  failure does NOT fail the build.
- Env-var name (`ZCCACHE_LINK_DEPLOY_CMD`) — not renaming.
- Payload: single absolute path as argv[1].

A note in `README.md` documenting the hook would also be welcome so
other downstreams can use it.

### 3. Confirm or unadvertise `clang-tidy` + IWYU support

README lines 17-18, 121-122, 626 advertise `clang-tidy` and IWYU (aka
`include-what-you-use`). Source-grep on `main` shows zero references to
either. My assumption is they fall through as generic clang-family
dispatches, which might work for `clang-tidy -p build foo.cpp` but is
unverified.

Preferences (pick one):

- **Option A:** add minimal integration tests confirming cache-hit path
  works for `clang-tidy` and `include-what-you-use` with typical args,
  keep README as-is.
- **Option B:** remove those items from the README until they're
  tested.

Either is fine; we just need to know whether to ship
`clang-tool-chain-clang-tidy` / `-iwyu` on top of zccache right now or
defer them.

---

Happy to help land any of these — point me at a draft PR if easier.

Thanks!
