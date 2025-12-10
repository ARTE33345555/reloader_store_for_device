// Core/pkg_core.h
#ifndef PKG_CORE_H
#define PKG_CORE_H

#include <stddef.h>
#include <stdint.h>

// Simple result codes
typedef enum {
    PKG_OK = 0,
    PKG_ERR_INVALID = 1,
    PKG_ERR_HASH_MISMATCH = 2,
    PKG_ERR_IO = 3
} pkg_result_t;

// SHA-256 (minimal interface; implement or link a known-good SHA256)
void sha256(const uint8_t *data, size_t len, uint8_t out[32]);

// Hex helpers
void to_hex(const uint8_t *buf, size_t len, char *out);          // out size >= len*2+1
int  equals_hex_ci(const char *a, const char *b);                 // case-insensitive compare

// File hashing + verify
pkg_result_t file_sha256_hex(const char *path, char *out_hex, size_t out_size);
pkg_result_t verify_file_hash(const char *path, const char *expected_hex);

#endif
