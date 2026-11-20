"""Reviewed logical binding and the frozen files this adapter must not rewrite."""

LOGICAL_GIT = "d4a096667bcf4dd7e3f27070f9dba403256d4ad2"
LOGICAL_SOURCE = "530967f0412acdac93b438cd7b0965ee0767d408df068d596200b1af31a24931"

# Delivery commits that carry docs or dist manifests. None of them is the logical source.
DELIVERY_GIT = frozenset({
    "1cc1a279a0d1d2cd3ec907bf818f5c5451249acb",
    "1f1664e661d2b9de0a91a31a53afa54281870133",
    "a61d2464884ad84eab6483ff9be0d7e09e55e554",
    "732138ec210e142be4795004eee53edfbcd7fd83",
})

OLD_STRICT_GIT = "80d1d1fe4af4a374808c1022c74278cf8b7f8d4a"
OLD_STRICT_SOURCE = "8826430a8895bd90fc2242e9844d124c650c3ccb0850b93c77a3a3230a7e2551"
OLD_V3_GIT = "c7c891955e6402bf566af47f5a2dc37925cff7df"
OLD_V3_SOURCE = "da5dbe0b30b5eaa2d31d550d3db6f56a6d1f26f6cd4e9a5666f4965e7abffdc4"

RETIRED_PORTS = frozenset({8931, 8932, 8933, 8934, 8935})

FROZEN_GUARD_SHA256 = "565b321b4f2773d100be570642d0eb8a003f1fa68ed1e429921d36a5a3ce3526"
FROZEN_BOOTSTRAP_SHA256 = "fab44c9a26114200fcc0b21f29e92db1dfce7c166e3da8684dd709847f2557ff"
FROZEN_LAUNCHER_SHA256 = "8b57e33e5c194ffb39d6e092e71a6b2352e52e8b2e2b94156bcd585d42a8bc20"

OLD_HOMES = (
    "/workspace/comfyart-authority-1004",
    "/workspace/wt_1008_final_c7c89195",
    "/workspace/1013-full-bootstrap-quote",
)

# Flags the old strict launcher set. The adapter rejects them and never acts on them.
PROBE_ENV_FLAGS = (
    "COMFYART_QUOTE_PROBE_EXECUTE",
    "COMFYART_CONTROLLED_PRECHECK_ONLY",
)

# Present in an environment, these must not be forwarded. The launcher refuses instead of copying them.
CREDENTIAL_ENV = (
    "WAVESPEED_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
)
