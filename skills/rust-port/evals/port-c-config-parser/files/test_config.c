#include "config.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void test_basic(void) {
    int code, line;
    config_t *c = config_parse("name = app\n# comment\n; also comment\n\n[db]\nport=5432\nhost = localhost \n",
                               CONFIG_TRIM_VALUES, &code, &line);
    assert(c && code == CONFIG_OK);
    assert(config_count(c) == 3);
    assert(strcmp(config_get(c, "name"), "app") == 0);
    assert(strcmp(config_get(c, "db.host"), "localhost") == 0);
    long port;
    assert(config_get_int(c, "db.port", &port) == CONFIG_INT_OK && port == 5432);
    assert(config_get(c, "missing") == NULL);
    config_free(c);
}

static void test_untrimmed_values_keep_whitespace(void) {
    config_t *c = config_parse("k =  v \n", 0, NULL, NULL);
    assert(c && strcmp(config_get(c, "k"), "  v") == 0); /* line trim removes the trailing space */
    config_free(c);
}

static void test_get_int_errors(void) {
    config_t *c = config_parse("a=12x\nb=\nc=-7\nd=99999999999999999999\n", 0, NULL, NULL);
    long n = 0;
    assert(config_get_int(c, "a", &n) == CONFIG_INT_NOT_NUMBER);
    assert(config_get_int(c, "b", &n) == CONFIG_INT_NOT_NUMBER);
    assert(config_get_int(c, "c", &n) == CONFIG_INT_OK && n == -7);
    assert(config_get_int(c, "d", &n) == CONFIG_INT_NOT_NUMBER);
    assert(config_get_int(c, "zzz", &n) == CONFIG_INT_MISSING);
    config_free(c);
}

static void test_duplicates(void) {
    int code, line;
    assert(config_parse("a=1\nb=2\na=3\n", 0, &code, &line) == NULL);
    assert(code == CONFIG_ERR_DUPLICATE && line == 3);
    config_t *c = config_parse("a=1\na=3\n", CONFIG_ALLOW_DUPLICATES, &code, &line);
    assert(c && config_count(c) == 1 && strcmp(config_get(c, "a"), "3") == 0);
    config_free(c);
}

static void test_case_insensitive(void) {
    config_t *c = config_parse("[Server]\nPort=80\n", CONFIG_CASE_INSENSITIVE, NULL, NULL);
    assert(strcmp(config_get(c, "server.port"), "80") == 0);
    config_free(c);
    int code;
    assert(config_parse("A=1\na=2\n", CONFIG_CASE_INSENSITIVE, &code, NULL) == NULL && code == CONFIG_ERR_DUPLICATE);
}

static void test_syntax_errors(void) {
    int code, line;
    assert(config_parse("ok=1\nnot a pair\n", 0, &code, &line) == NULL && code == CONFIG_ERR_SYNTAX && line == 2);
    assert(config_parse("[unclosed\n", 0, &code, &line) == NULL && code == CONFIG_ERR_SYNTAX && line == 1);
    assert(config_parse("[]\n", 0, &code, &line) == NULL && code == CONFIG_ERR_SYNTAX);
    assert(config_parse("=novalue\n", 0, &code, &line) == NULL && code == CONFIG_ERR_SYNTAX);
}

static void test_empty_input(void) {
    config_t *c = config_parse("", 0, NULL, NULL);
    assert(c && config_count(c) == 0);
    config_free(c);
}

int main(void) {
    test_basic();
    test_untrimmed_values_keep_whitespace();
    test_get_int_errors();
    test_duplicates();
    test_case_insensitive();
    test_syntax_errors();
    test_empty_input();
    puts("all config tests passed");
    return 0;
}
