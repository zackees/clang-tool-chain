# Parallel Downloads with Range Requests

**High-speed downloads using multi-threaded HTTP range requests for faster toolchain installation.**

## Overview

Starting with version 1.0.14+, `clang-tool-chain` uses intelligent parallel downloading with HTTP range requests to significantly speed up toolchain installation. This feature provides **3-5x faster downloads** for large files when the server supports range requests (which GitHub LFS does).

### Performance Improvements

| File Size | Single-threaded | Parallel (6 workers) | Speedup |
|-----------|----------------|---------------------|---------|
| 100 MB    | ~35-40s        | ~8-12s             | **3-5x** |
| 200 MB    | ~70-80s        | ~16-24s            | **3-5x** |
| 400 MB    | ~140-160s      | ~32-48s            | **3-5x** |

*Times based on typical 100 Mbps connection. Actual performance varies by network speed and server capabilities.*

## How It Works

### Automatic Server Detection

The downloader automatically:
1. **Checks server capabilities** via HEAD request to detect Accept-Ranges header
2. **Determines file size** from Content-Length header
3. **Decides download strategy** based on server support and file size
4. **Falls back gracefully** to single-threaded download if needed

### Intelligent Download Strategy

**Uses parallel download when:**
- Server supports HTTP range requests (Accept-Ranges: bytes)
- File size is known (Content-Length header present)
- File is larger than 10 MB (configurable)

**Falls back to single-threaded when:**
- Server doesn't support range requests
- File size is unknown
- File is smaller than threshold
- Any errors occur during parallel download

### Multi-threaded Range Requests

For large files, the downloader:
1. **Splits file into chunks** (8 MB default)
2. **Downloads chunks in parallel** using 6 concurrent workers (default)
3. **Pre-allocates file** and writes chunks to correct positions
4. **Verifies checksums** after download completes

## Configuration

### Environment Variables

Fine-tune parallel download behavior via environment variables:

```bash
# Disable parallel downloads (use single-threaded fallback)
export CLANG_TOOL_CHAIN_DISABLE_PARALLEL=1

# Configure chunk size in MB (default: 8)
export CLANG_TOOL_CHAIN_CHUNK_SIZE=4

# Configure number of parallel workers (default: 6)
export CLANG_TOOL_CHAIN_MAX_WORKERS=8

# Configure minimum file size for parallel download in MB (default: 10)
export CLANG_TOOL_CHAIN_MIN_SIZE=20
```

**Windows PowerShell:**
```powershell
$env:CLANG_TOOL_CHAIN_CHUNK_SIZE="4"
$env:CLANG_TOOL_CHAIN_MAX_WORKERS="8"
```

**Windows Command Prompt:**
```cmd
set CLANG_TOOL_CHAIN_CHUNK_SIZE=4
set CLANG_TOOL_CHAIN_MAX_WORKERS=8
```

### Recommended Settings

**Fast connections (>100 Mbps):**
```bash
export CLANG_TOOL_CHAIN_CHUNK_SIZE=8      # 8 MB chunks
export CLANG_TOOL_CHAIN_MAX_WORKERS=8     # 8 parallel workers
```

**Slow/unstable connections:**
```bash
export CLANG_TOOL_CHAIN_CHUNK_SIZE=4      # 4 MB chunks
export CLANG_TOOL_CHAIN_MAX_WORKERS=4     # 4 parallel workers
```

**Debugging issues:**
```bash
export CLANG_TOOL_CHAIN_DISABLE_PARALLEL=1  # Disable parallel downloads
```

## Technical Details

### Architecture

**Module:** `src/clang_tool_chain/parallel_download.py`

**Key Components:**

1. **Server Capability Detection**
   - HEAD request to check Accept-Ranges header
   - Content-Length parsing for file size
   - Automatic fallback for servers without range support

2. **Chunk Calculation**
   - Splits file into equal-sized chunks
   - Handles uneven divisions (last chunk may be smaller)
   - Calculates optimal chunk boundaries

3. **Parallel Download**
   - ThreadPoolExecutor for concurrent downloads
   - Each worker downloads specific byte range
   - Pre-allocated file with positioned writes

4. **Error Handling**
   - Automatic retry for failed chunks
   - Graceful fallback to single-threaded
   - Comprehensive error reporting

### Thread Safety

- Uses `threading.Lock` for synchronized file writes
- Each chunk writes to specific file position using `seek()`
- No race conditions or data corruption

### Checksum Verification

- SHA256 verification after download completes
- Same verification as single-threaded download
- Temporary file cleaned up if verification fails

## GitHub LFS Compatibility

The parallel download feature is optimized for **GitHub LFS** (Large File Storage):

- ✅ GitHub LFS fully supports HTTP range requests
- ✅ Excellent performance with parallel downloads
- ✅ Stable connection handling
- ✅ Reliable Content-Length headers

**This is why parallel downloads work seamlessly with the LFS migration.**

## Troubleshooting

### Slow downloads despite parallel support

**Problem:** Downloads are still slow even with parallel enabled

**Solutions:**
1. Check network speed: `speedtest-cli`
2. Increase workers: `export CLANG_TOOL_CHAIN_MAX_WORKERS=8`
3. Increase chunk size: `export CLANG_TOOL_CHAIN_CHUNK_SIZE=16`

### Connection errors or timeouts

**Problem:** Downloads fail with connection errors

**Solutions:**
1. Reduce workers: `export CLANG_TOOL_CHAIN_MAX_WORKERS=3`
2. Reduce chunk size: `export CLANG_TOOL_CHAIN_CHUNK_SIZE=4`
3. Disable parallel: `export CLANG_TOOL_CHAIN_DISABLE_PARALLEL=1`

### Checksum verification failures

**Problem:** Downloads complete but checksum fails

**Solutions:**
1. This indicates corrupted download or network issues
2. Retry the download (automatic on next run)
3. Check network stability
4. If persistent, disable parallel: `export CLANG_TOOL_CHAIN_DISABLE_PARALLEL=1`

### Debugging

**Enable verbose logging to see download details:**

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Look for log messages like:**
```
Server capabilities: ranges=True, size=104.86 MB, partial=True
Downloading in 13 chunks using 6 workers
Chunk 1/13 complete: 8.00 MB
Chunk 2/13 complete: 8.00 MB
...
Download complete: 104.86 MB
Checksum verification passed
```

## Comparison with Other Tools

### vs. aria2c

**aria2c (external tool):**
- ✅ Very fast multi-connection downloads
- ✅ Mature and battle-tested
- ❌ Requires external binary distribution
- ❌ Cross-platform maintenance burden
- ❌ Additional dependency

**clang-tool-chain parallel downloads:**
- ✅ Built-in, no external dependencies
- ✅ Pure Python (stdlib only)
- ✅ Automatic fallback
- ✅ Same codebase maintains all platforms
- ⚠️ Slightly slower than aria2c

**Decision:** Built-in parallel downloads provide the best balance of speed and maintainability.

### vs. Single-threaded urllib

**Standard urllib.request:**
- ✅ Simple and reliable
- ✅ No additional code
- ❌ 3-5x slower for large files
- ❌ No resume capability
- ❌ Single connection per download

**Parallel downloads:**
- ✅ 3-5x faster for large files
- ✅ Resume capability (future feature)
- ✅ Better bandwidth utilization
- ⚠️ Slightly more complex

## Future Enhancements

Potential improvements for future versions:

1. **Resume interrupted downloads** - Save chunk state and resume from last position
2. **Adaptive chunk sizing** - Dynamically adjust chunk size based on network performance
3. **Connection pooling** - Reuse connections across chunks for better performance
4. **Progress callbacks** - Real-time progress reporting with estimated time remaining
5. **Bandwidth limiting** - Optional download speed limit for constrained networks

## See Also

- [Architecture Documentation](ARCHITECTURE.md) - Overall system architecture
- [Testing Guide](TESTING.md) - Running parallel download tests
- [Maintainer Guide](MAINTAINER.md) - Creating binary distributions

## References

- [HTTP Range Requests (RFC 7233)](https://datatracker.ietf.org/doc/html/rfc7233)
- [GitHub LFS Specification](https://github.com/git-lfs/git-lfs/blob/main/docs/spec.md)
- [Python ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor)
