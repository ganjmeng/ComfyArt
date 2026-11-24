"""Identity pins for the offline startup adapter.

LOGICAL_SOURCE is the api/bot/__init__.py digest after the singular price body,
the multi-angle quote snapshot join, the confirmed preview-plus-finals plan,
and the confirmed progress block. It is not a git SHA. The delivery commit is
not stored here. Parent
main 72f387a8 still has the old plural body and must not be accepted.
"""

# Not a commit SHA. Binding is LOGICAL_SOURCE. Do not replace this with the delivery SHA.
LOGICAL_GIT = "singular-price-input"
LOGICAL_SOURCE = "c83a272eaf4001960ff7cc6952fef0d24754999d2ddf41bf9c9401d267e6fd42"
STALE_MAIN_GIT = "72f387a87ec31530b3e9ef2682f0fec33d74b11a"
STALE_MAIN_SOURCE = "90cc5bd7c9883fa3eeea6037210931afc44464d75bf179dcd3959ebe45dc5c2f"

# Earlier protection-recovery commits. They are not this product tree.
RECOVERY_GIT = frozenset({
    "d4a096667bcf4dd7e3f27070f9dba403256d4ad2",
    "1cc1a279a0d1d2cd3ec907bf818f5c5451249acb",
    "1f1664e661d2b9de0a91a31a53afa54281870133",
    "a61d2464884ad84eab6483ff9be0d7e09e55e554",
    "732138ec210e142be4795004eee53edfbcd7fd83",
    "738ddbf19c71890ca1820f26e4a7e8852685ebd7",
    "041f13009125f7605bb9254f06a6e470b4d03891",
})
RECOVERY_SOURCE = "530967f0412acdac93b438cd7b0965ee0767d408df068d596200b1af31a24931"

OLD_STRICT_GIT = "80d1d1fe4af4a374808c1022c74278cf8b7f8d4a"
OLD_STRICT_SOURCE = "8826430a8895bd90fc2242e9844d124c650c3ccb0850b93c77a3a3230a7e2551"
OLD_V3_GIT = "c7c891955e6402bf566af47f5a2dc37925cff7df"

RETIRED_PORTS = frozenset({8931, 8932, 8933, 8934, 8935})

FROZEN_GUARD_SHA256 = "565b321b4f2773d100be570642d0eb8a003f1fa68ed1e429921d36a5a3ce3526"
FROZEN_BOOTSTRAP_SHA256 = "fab44c9a26114200fcc0b21f29e92db1dfce7c166e3da8684dd709847f2557ff"
FROZEN_LAUNCHER_SHA256 = "8b57e33e5c194ffb39d6e092e71a6b2352e52e8b2e2b94156bcd585d42a8bc20"

OLD_HOMES = (
    "/workspace/comfyart-authority-1004",
    "/workspace/wt_1008_final_c7c89195",
    "/workspace/1013-full-bootstrap-quote",
)

PROBE_ENV_FLAGS = (
    "COMFYART_QUOTE_PROBE_EXECUTE",
    "COMFYART_CONTROLLED_PRECHECK_ONLY",
)

CREDENTIAL_ENV = (
    "WAVESPEED_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
)
