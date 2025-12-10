// Core/pkg_core.c
#include "pkg_core.h"
#include <stdio.h>
#include <ctype.h>
#include <string.h>
#include <stdlib.h>

// ---- Minimal SHA-256 reference or link your preferred implementation ----
// Placeholder: not a real SHA-256. Replace with a proper SHA-256 function!
void sha256(const uint8_t *data, size_t len, uint8_t out[32]) {
    // Implement or link a real SHA-256 (e.g., mbedTLS/OpenSSL, or a small public domain impl).
    // For now fill zeros to indicate "unimplemented".
    memset(out, 0, 32);
}

void to_hex(const uint8_t *buf, size_t len, char *out) {
    static const char *hex = "0123456789abcdef";
    for (size_t i = 0; i < len; i++) {
        out[i*2]     = hex[(buf[i] >> 4) & 0xF];
        out[i*2 + 1] = hex[buf[i] & 0xF];
    }
    out[len*2] = '\0';
}

int equals_hex_ci(const char *a, const char *b) {
    if (!a || !b) return 0;
    size_t la = strlen(a), lb = strlen(b);
    if (la != lb) return 0;
    for (size_t i = 0; i < la; i++) {
        char ca = tolower((unsigned char)a[i]);
        char cb = tolower((unsigned char)b[i]);
        if (ca != cb) return 0;
    }
    return 1;
}

pkg_result_t file_sha256_hex(const char *path, char *out_hex, size_t out_size) {
    if (!path || !out_hex || out_size < 65) return PKG_ERR_INVALID;

    FILE *f = fopen(path, "rb");
    if (!f) return PKG_ERR_IO;

    // Read file into memory (for simplicity). For large files, stream in blocks.
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (len < 0) { fclose(f); return PKG_ERR_IO; }

    uint8_t *buf = (uint8_t*)malloc((size_t)len);
    if (!buf) { fclose(f); return PKG_ERR_IO; }

    size_t rd = fread(buf, 1, (size_t)len, f);
    fclose(f);
    if (rd != (size_t)len) { free(buf); return PKG_ERR_IO; }

    uint8_t digest[32];
    sha256(buf, (size_t)len, digest);
    free(buf);

    to_hex(digest, 32, out_hex);
    return PKG_OK;
}

pkg_result_t verify_file_hash(const char *path, const char *expected_hex) {
    char actual[65];
    pkg_result_t r = file_sha256_hex(path, actual, sizeof(actual));
    if (r != PKG_OK) return r;
    return equals_hex_ci(actual, expected_hex) ? PKG_OK : PKG_ERR_HASH_MISMATCH;
}
