/*
 * tongsuo_sig_bridge.c — SM2 签名薄层 C 桥接
 *
 * 将 Tongsuo 的 SM2 签名 API 封装为 3 个简单函数，
 * 供 Python ctypes 直接调用。
 *
 * 实现策略：
 *   keygen: EVP_PKEY_Q_keygen("SM2") → 提取 pk/sk 字节
 *   sign:   EC_KEY 从 sk 重建 → EVP_DigestSign (SM3)
 *   verify: EC_KEY 从 pk 重建 → EVP_DigestVerify (SM3)
 *
 * 注: Tongsuo 的 EVP_PKEY_fromdata 对 SM2 不工作（返回 NULL），
 * 因此签名和验签使用 EC_KEY 旧版 API 从原始字节重建密钥。
 * 该 API 在 OpenSSL/Tongsuo 3.x 中标记为 deprecated 但仍然可用。
 *
 * 签名格式: DER 编码的 SM2 签名，最大 72 字节。
 * 公钥格式: 未压缩点 04||x(32B)||y(32B)，65 字节。
 * 私钥格式: 原始字节 32 字节。
 */

#include <openssl/evp.h>
#include <openssl/ec.h>
#include <openssl/core_names.h>
#include <openssl/params.h>
#include <string.h>
#include <stdlib.h>

#define SM2_PK_SIZE 65
#define SM2_SK_SIZE 32
#define SM2_SIG_MAX_SIZE 72
#define SM2_DEFAULT_ID "1234567812345678"
#define SM2_DEFAULT_ID_LEN 16

static int _sm2_set_ctx_id(EVP_PKEY_CTX *pctx)
{
    if (!pctx) return 0;
    return EVP_PKEY_CTX_set1_id(pctx,
        (const unsigned char *)SM2_DEFAULT_ID, SM2_DEFAULT_ID_LEN);
}

int tongsuo_sm2_keygen(
    unsigned char *out_pk, int *out_pk_len,
    unsigned char *out_sk, int *out_sk_len,
    int pk_buf_size, int sk_buf_size)
{
    EVP_PKEY *pkey = EVP_PKEY_Q_keygen(NULL, NULL, "SM2");
    if (!pkey) return -1;

    int rc = -2;

    unsigned char *pk_ptr = NULL;
    size_t pk_len = EVP_PKEY_get1_encoded_public_key(pkey, &pk_ptr);
    if (pk_len == 0 || (int)pk_len > pk_buf_size) {
        if (pk_ptr) OPENSSL_free(pk_ptr);
        goto done;
    }
    memcpy(out_pk, pk_ptr, pk_len);
    *out_pk_len = (int)pk_len;
    OPENSSL_free(pk_ptr);

    EC_KEY *ec = EVP_PKEY_get0_EC_KEY(pkey);
    if (!ec) goto done;

    const BIGNUM *bn_priv = EC_KEY_get0_private_key(ec);
    if (!bn_priv) goto done;

    int bn_len = BN_num_bytes(bn_priv);
    if (bn_len > sk_buf_size || bn_len > SM2_SK_SIZE) goto done;

    memset(out_sk, 0, SM2_SK_SIZE);
    BN_bn2bin(bn_priv, out_sk + (SM2_SK_SIZE - bn_len));
    *out_sk_len = SM2_SK_SIZE;

    rc = 0;
done:
    EVP_PKEY_free(pkey);
    return rc;
}

static EVP_PKEY *_sm2_pkey_from_private_key(
    const unsigned char *sk, int sk_len)
{
    EC_KEY *eckey = EC_KEY_new_by_curve_name(NID_sm2);
    if (!eckey) return NULL;

    BIGNUM *bn_priv = BN_bin2bn(sk, sk_len, NULL);
    if (!bn_priv) { EC_KEY_free(eckey); return NULL; }

    if (EC_KEY_set_private_key(eckey, bn_priv) != 1) {
        BN_free(bn_priv);
        EC_KEY_free(eckey);
        return NULL;
    }

    const EC_GROUP *group = EC_KEY_get0_group(eckey);
    EC_POINT *pub_point = EC_POINT_new(group);
    if (!pub_point) {
        BN_free(bn_priv);
        EC_KEY_free(eckey);
        return NULL;
    }

    if (EC_POINT_mul(group, pub_point, bn_priv, NULL, NULL, NULL) != 1) {
        EC_POINT_free(pub_point);
        BN_free(bn_priv);
        EC_KEY_free(eckey);
        return NULL;
    }

    if (EC_KEY_set_public_key(eckey, pub_point) != 1) {
        EC_POINT_free(pub_point);
        BN_free(bn_priv);
        EC_KEY_free(eckey);
        return NULL;
    }
    EC_POINT_free(pub_point);
    BN_free(bn_priv);

    EVP_PKEY *pkey = EVP_PKEY_new();
    if (!pkey) { EC_KEY_free(eckey); return NULL; }

    if (EVP_PKEY_assign_EC_KEY(pkey, eckey) != 1) {
        EVP_PKEY_free(pkey);
        return NULL;
    }

    return pkey;
}

static EVP_PKEY *_sm2_pkey_from_public_key(
    const unsigned char *pk, int pk_len)
{
    EC_KEY *eckey = EC_KEY_new_by_curve_name(NID_sm2);
    if (!eckey) return NULL;

    const EC_GROUP *group = EC_KEY_get0_group(eckey);
    EC_POINT *point = EC_POINT_new(group);
    if (!point) { EC_KEY_free(eckey); return NULL; }

    if (EC_POINT_oct2point(group, point, pk, (size_t)pk_len, NULL) != 1) {
        EC_POINT_free(point);
        EC_KEY_free(eckey);
        return NULL;
    }

    if (EC_KEY_set_public_key(eckey, point) != 1) {
        EC_POINT_free(point);
        EC_KEY_free(eckey);
        return NULL;
    }
    EC_POINT_free(point);

    EVP_PKEY *pkey = EVP_PKEY_new();
    if (!pkey) { EC_KEY_free(eckey); return NULL; }

    if (EVP_PKEY_assign_EC_KEY(pkey, eckey) != 1) {
        EVP_PKEY_free(pkey);
        return NULL;
    }

    return pkey;
}

int tongsuo_sm2_sign(
    const unsigned char *sk, int sk_len,
    const unsigned char *msg, int msg_len,
    unsigned char *out_sig, int *out_sig_len,
    int sig_buf_size)
{
    EVP_PKEY *pkey = _sm2_pkey_from_private_key(sk, sk_len);
    if (!pkey) return -1;

    int rc = -2;
    EVP_MD_CTX *mdctx = EVP_MD_CTX_new();
    EVP_PKEY_CTX *pctx = NULL;
    if (!mdctx) goto cleanup1;

    if (EVP_DigestSignInit(mdctx, &pctx, EVP_sm3(), NULL, pkey) != 1) goto cleanup2;
    if (pctx && _sm2_set_ctx_id(pctx) != 1) goto cleanup2;
    if (EVP_DigestSignUpdate(mdctx, msg, (size_t)msg_len) != 1) goto cleanup2;

    size_t sig_len = 0;
    if (EVP_DigestSignFinal(mdctx, NULL, &sig_len) != 1) goto cleanup2;
    if ((int)sig_len > sig_buf_size) goto cleanup2;

    if (EVP_DigestSignFinal(mdctx, out_sig, &sig_len) != 1) goto cleanup2;
    *out_sig_len = (int)sig_len;
    rc = 0;

cleanup2:
    EVP_MD_CTX_free(mdctx);
cleanup1:
    EVP_PKEY_free(pkey);
    return rc;
}

int tongsuo_sm2_verify(
    const unsigned char *pk, int pk_len,
    const unsigned char *msg, int msg_len,
    const unsigned char *sig, int sig_len)
{
    EVP_PKEY *pkey = _sm2_pkey_from_public_key(pk, pk_len);
    if (!pkey) return -1;

    int rc = -2;
    EVP_MD_CTX *mdctx = EVP_MD_CTX_new();
    EVP_PKEY_CTX *pctx = NULL;
    if (!mdctx) goto cleanup;

    if (EVP_DigestVerifyInit(mdctx, &pctx, EVP_sm3(), NULL, pkey) != 1) goto cleanup2;
    if (pctx && _sm2_set_ctx_id(pctx) != 1) goto cleanup2;
    if (EVP_DigestVerifyUpdate(mdctx, msg, (size_t)msg_len) != 1) goto cleanup2;

    rc = EVP_DigestVerifyFinal(mdctx, sig, (size_t)sig_len);

cleanup2:
    EVP_MD_CTX_free(mdctx);
cleanup:
    EVP_PKEY_free(pkey);
    return rc;
}
