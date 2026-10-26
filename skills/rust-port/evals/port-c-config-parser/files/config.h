#ifndef CONFIG_H
#define CONFIG_H

/* Parse flags, OR them together. */
#define CONFIG_TRIM_VALUES      0x1  /* strip whitespace around values */
#define CONFIG_ALLOW_DUPLICATES 0x2  /* later keys overwrite earlier ones instead of failing */
#define CONFIG_CASE_INSENSITIVE 0x4  /* keys are compared case-insensitively */

/* Error codes returned through err_code. */
#define CONFIG_OK              0
#define CONFIG_ERR_SYNTAX     -1
#define CONFIG_ERR_DUPLICATE  -2
#define CONFIG_ERR_NOMEM      -3

/* config_get_int return values. */
#define CONFIG_INT_OK          0
#define CONFIG_INT_MISSING    -1
#define CONFIG_INT_NOT_NUMBER -2

typedef struct config config_t;

/* Parses INI-style text. Returns NULL on failure and sets *err_code and *err_line
 * (1-based) if they are non-NULL. Sections become key prefixes: "[db]\nport=5"
 * defines "db.port". Lines starting with '#' or ';' are comments. */
config_t *config_parse(const char *text, int flags, int *err_code, int *err_line);

/* Returns the value for key, or NULL if absent. The pointer stays valid until
 * config_free. */
const char *config_get(const config_t *cfg, const char *key);

/* Parses the value for key as a base-10 long into *out. */
int config_get_int(const config_t *cfg, const char *key, long *out);

/* Number of keys. */
int config_count(const config_t *cfg);

void config_free(config_t *cfg);

#endif
