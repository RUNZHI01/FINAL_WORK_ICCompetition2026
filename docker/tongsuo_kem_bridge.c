/*
 * tongsuo_kem_bridge.c — ML-KEM 薄层 C 桥接
 *
 * 将 Tongsuo 的 EVP_PKEY KEM API 封装为 3 个简单函数，
 * 供 Python ctypes 直接调用，避免在 Python 端处理复杂的 EVP 对象生命周期。
 *
 * 策略：keygen 时同时执行封装，保存 shared_secret；decaps 时重新 keygen + decaps。
 * 这样 decaps 不需要从原始字节重建 EVP_PKEY。
 *
 * 编译:
 *   gcc -shared -fPIC -O2 -o libtongsuo_kem_bridge.so tongsuo_kem_bridge.c \
 *       -I/usr/local/tongsuo/include -L/usr/local/tongsuo/lib64 -lcrypto
 */

#include <openssl/evp.h>
#include <openssl/core_names.h>
#include <openssl/params.h>
#include <openssl/ml_kem.h>
#include <string.h>
#include <stdlib.h>

/*
 * keygen: 生成 ML-KEM 密钥对，提取原始公钥和私钥字节。
 *
 * 返回: 0 成功, 负数失败
 */
int tongsuo_kem_keygen(
    const char *alg,
    unsigned char *out_pk, int *out_pk_len,
    unsigned char *out_sk, int *out_sk_len,
    int pk_buf_size, int sk_buf_size)
{
    EVP_PKEY *pkey = EVP_PKEY_Q_keygen(NULL, NULL, alg);
    if (!pkey) return -1;

    int rc = -2;

    /* 提取公钥 */
    unsigned char *pk_ptr = NULL;
    size_t pk_len = EVP_PKEY_get1_encoded_public_key(pkey, &pk_ptr);
    if (pk_len == 0 || (int)pk_len > pk_buf_size) {
        if (pk_ptr) OPENSSL_free(pk_ptr);
        goto done;
    }
    memcpy(out_pk, pk_ptr, pk_len);
    *out_pk_len = (int)pk_len;
    OPENSSL_free(pk_ptr);

    /* 提取私钥：使用 EVP_PKEY_todata + OSSL_PARAM */
    OSSL_PARAM *params = NULL;
    if (EVP_PKEY_todata(pkey, EVP_PKEY_KEYPAIR, &params) != 1) goto done;

    /* Tongsuo 的 ML-KEM 私钥参数名为 "priv" */
    const OSSL_PARAM *p = OSSL_PARAM_locate_const(params, "priv");
    if (!p) p = OSSL_PARAM_locate_const(params, "seed");

    if (!p || p->data_type != OSSL_PARAM_OCTET_STRING) {
        OSSL_PARAM_free(params);
        goto done;
    }

    int sk_len = (int)p->data_size;
    if (sk_len > sk_buf_size) {
        OSSL_PARAM_free(params);
        goto done;
    }
    memcpy(out_sk, p->data, sk_len);
    *out_sk_len = sk_len;
    OSSL_PARAM_free(params);

    rc = 0;
done:
    EVP_PKEY_free(pkey);
    return rc;
}

/*
 * encaps: 使用公钥封装。
 *
 * 构造仅含公钥的 EVP_PKEY（通过 keygen 获取模板 + set1_encoded_public_key）。
 */
int tongsuo_kem_encaps(
    const char *alg,
    const unsigned char *pk, int pk_len,
    unsigned char *out_ct, int *out_ct_len,
    unsigned char *out_ss, int *out_ss_len,
    int ct_buf_size, int ss_buf_size)
{
    /* 生成一个临时密钥对获取参数模板 */
    EVP_PKEY *tmpl = EVP_PKEY_Q_keygen(NULL, NULL, alg);
    if (!tmpl) return -1;

    /* 构造仅含公钥的 PKEY */
    EVP_PKEY *pkey = EVP_PKEY_new();
    if (!pkey) { EVP_PKEY_free(tmpl); return -1; }

    EVP_PKEY_copy_parameters(pkey, tmpl);
    EVP_PKEY_free(tmpl);

    if (EVP_PKEY_set1_encoded_public_key(pkey, pk, (size_t)pk_len) != 1) {
        EVP_PKEY_free(pkey);
        return -2;
    }

    int rc = -3;
    EVP_PKEY_CTX *ctx = EVP_PKEY_CTX_new_from_pkey(NULL, pkey, NULL);
    if (!ctx) goto done1;

    if (EVP_PKEY_encapsulate_init(ctx, NULL) != 1) goto done2;

    /* 先查询输出尺寸 */
    size_t ct_len = 0, ss_len = 0;
    if (EVP_PKEY_encapsulate(ctx, NULL, &ct_len, NULL, &ss_len) != 1) goto done2;
    if ((int)ct_len > ct_buf_size || (int)ss_len > ss_buf_size) goto done2;

    /* 执行封装 */
    if (EVP_PKEY_encapsulate(ctx, out_ct, &ct_len, out_ss, &ss_len) != 1) goto done2;
    *out_ct_len = (int)ct_len;
    *out_ss_len = (int)ss_len;
    rc = 0;

done2:
    EVP_PKEY_CTX_free(ctx);
done1:
    EVP_PKEY_free(pkey);
    return rc;
}

/*
 * decaps: 使用密文和完整的 EVP_PKEY（从私钥重建）解封装。
 *
 * ML-KEM 的 EVP_PKEY_fromdata 需要 priv + pub 同时提供。
 * 因此 decaps 需要同时接收 sk 和 pk 的原始字节。
 */
int tongsuo_kem_decaps(
    const char *alg,
    const unsigned char *sk, int sk_len,
    const unsigned char *pk, int pk_len,
    const unsigned char *ct, int ct_len,
    unsigned char *out_ss, int *out_ss_len,
    int ss_buf_size)
{
    int rc = -1;

    /* ML-KEM 的 fromdata 需要 priv + pub 两个参数 */
    OSSL_PARAM params[3];
    memset(params, 0, sizeof(params));

    params[0] = OSSL_PARAM_construct_octet_string("priv", (void *)sk, (size_t)sk_len);
    params[1] = OSSL_PARAM_construct_octet_string("pub", (void *)pk, (size_t)pk_len);
    params[2] = OSSL_PARAM_construct_end();

    EVP_PKEY_CTX *kctx = EVP_PKEY_CTX_new_from_name(NULL, alg, NULL);
    if (!kctx) return -1;

    if (EVP_PKEY_fromdata_init(kctx) != 1) {
        EVP_PKEY_CTX_free(kctx);
        return -2;
    }

    EVP_PKEY *pkey = NULL;
    if (EVP_PKEY_fromdata(kctx, &pkey, EVP_PKEY_KEYPAIR, params) != 1) {
        EVP_PKEY_CTX_free(kctx);
        return -3;
    }
    EVP_PKEY_CTX_free(kctx);

    if (!pkey) return -4;

    EVP_PKEY_CTX *ctx = EVP_PKEY_CTX_new_from_pkey(NULL, pkey, NULL);
    if (!ctx) goto done1;

    if (EVP_PKEY_decapsulate_init(ctx, NULL) != 1) goto done2;

    size_t ss_len = 32;
    if ((int)ss_len > ss_buf_size) goto done2;
    if (EVP_PKEY_decapsulate(ctx, out_ss, &ss_len, ct, (size_t)ct_len) != 1) goto done2;
    *out_ss_len = (int)ss_len;
    rc = 0;

done2:
    EVP_PKEY_CTX_free(ctx);
done1:
    EVP_PKEY_free(pkey);
    return rc;
}
