#include "config.h"
#include <ctype.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#define MAX_LINE 256

typedef struct {
    char *key;
    char *value;
} entry_t;

struct config {
    entry_t *entries;
    int count;
    int cap;
    int flags;
};

static char *dup_range(const char *start, const char *end) {
    size_t n = (size_t)(end - start);
    char *s = malloc(n + 1);
    if (!s) return NULL;
    memcpy(s, start, n);
    s[n] = '\0';
    return s;
}

static void trim(const char **start, const char **end) {
    while (*start < *end && isspace((unsigned char)**start)) (*start)++;
    while (*end > *start && isspace((unsigned char)*(*end - 1))) (*end)--;
}

static int find(const config_t *cfg, const char *key) {
    for (int i = 0; i < cfg->count; i++) {
        int same = (cfg->flags & CONFIG_CASE_INSENSITIVE)
                       ? strcasecmp(cfg->entries[i].key, key) == 0
                       : strcmp(cfg->entries[i].key, key) == 0;
        if (same) return i;
    }
    return -1;
}

static int put(config_t *cfg, char *key, char *value) {
    int i = find(cfg, key);
    if (i >= 0) {
        if (!(cfg->flags & CONFIG_ALLOW_DUPLICATES)) {
            free(key);
            free(value);
            return CONFIG_ERR_DUPLICATE;
        }
        free(cfg->entries[i].value);
        free(key);
        cfg->entries[i].value = value;
        return CONFIG_OK;
    }
    if (cfg->count == cfg->cap) {
        int cap = cfg->cap ? cfg->cap * 2 : 8;
        entry_t *grown = realloc(cfg->entries, (size_t)cap * sizeof(entry_t));
        if (!grown) {
            free(key);
            free(value);
            return CONFIG_ERR_NOMEM;
        }
        cfg->entries = grown;
        cfg->cap = cap;
    }
    cfg->entries[cfg->count].key = key;
    cfg->entries[cfg->count].value = value;
    cfg->count++;
    return CONFIG_OK;
}

static void fail(int *err_code, int *err_line, int code, int line) {
    if (err_code) *err_code = code;
    if (err_line) *err_line = line;
}

config_t *config_parse(const char *text, int flags, int *err_code, int *err_line) {
    config_t *cfg = calloc(1, sizeof(config_t));
    if (!cfg) {
        fail(err_code, err_line, CONFIG_ERR_NOMEM, 0);
        return NULL;
    }
    cfg->flags = flags;
    char section[MAX_LINE] = "";
    int line_no = 0;
    const char *p = text;
    while (*p) {
        line_no++;
        const char *eol = strchr(p, '\n');
        if (!eol) eol = p + strlen(p);
        const char *s = p, *e = eol;
        trim(&s, &e);
        if (s == e || *s == '#' || *s == ';') {
            /* blank or comment */
        } else if (*s == '[') {
            if (*(e - 1) != ']' || e - s < 3 || (size_t)(e - s - 2) >= sizeof(section)) {
                fail(err_code, err_line, CONFIG_ERR_SYNTAX, line_no);
                config_free(cfg);
                return NULL;
            }
            memcpy(section, s + 1, (size_t)(e - s - 2));
            section[e - s - 2] = '\0';
        } else {
            const char *eq = memchr(s, '=', (size_t)(e - s));
            if (!eq || eq == s) {
                fail(err_code, err_line, CONFIG_ERR_SYNTAX, line_no);
                config_free(cfg);
                return NULL;
            }
            const char *ks = s, *ke = eq;
            trim(&ks, &ke);
            const char *vs = eq + 1, *ve = e;
            if (flags & CONFIG_TRIM_VALUES) trim(&vs, &ve);
            char *key;
            if (section[0]) {
                size_t sl = strlen(section), kl = (size_t)(ke - ks);
                key = malloc(sl + 1 + kl + 1);
                if (key) {
                    memcpy(key, section, sl);
                    key[sl] = '.';
                    memcpy(key + sl + 1, ks, kl);
                    key[sl + 1 + kl] = '\0';
                }
            } else {
                key = dup_range(ks, ke);
            }
            char *value = dup_range(vs, ve);
            if (!key || !value) {
                free(key);
                free(value);
                fail(err_code, err_line, CONFIG_ERR_NOMEM, line_no);
                config_free(cfg);
                return NULL;
            }
            int rc = put(cfg, key, value);
            if (rc != CONFIG_OK) {
                fail(err_code, err_line, rc, line_no);
                config_free(cfg);
                return NULL;
            }
        }
        p = *eol ? eol + 1 : eol;
    }
    fail(err_code, err_line, CONFIG_OK, 0);
    return cfg;
}

const char *config_get(const config_t *cfg, const char *key) {
    int i = find(cfg, key);
    return i >= 0 ? cfg->entries[i].value : NULL;
}

int config_get_int(const config_t *cfg, const char *key, long *out) {
    const char *v = config_get(cfg, key);
    if (!v) return CONFIG_INT_MISSING;
    char *end;
    errno = 0;
    long n = strtol(v, &end, 10);
    if (end == v || *end != '\0' || errno == ERANGE) return CONFIG_INT_NOT_NUMBER;
    *out = n;
    return CONFIG_INT_OK;
}

int config_count(const config_t *cfg) { return cfg->count; }

void config_free(config_t *cfg) {
    if (!cfg) return;
    for (int i = 0; i < cfg->count; i++) {
        free(cfg->entries[i].key);
        free(cfg->entries[i].value);
    }
    free(cfg->entries);
    free(cfg);
}
