###############################################################################
# tests/infra/test.tfvars
#
# Fake-but-syntactically-valid values used by the pytest infra suite to drive
# `tofu validate` and to stand in for the variables module's required inputs.
# These values are NEVER applied — `tofu init -backend=false` keeps state out
# of the picture and we never run `tofu apply` from tests.
#
# Real production values live in infra/dev-tier/terraform.tfvars (gitignored)
# or in CI's TF_VAR_* env vars.
###############################################################################

# GCP — values shaped like real ones so any provider validation passes.
gcp_project_id = "agent-test-fake-project"
gcp_region     = "us-central1"

# Neon — fake but well-formed.
neon_api_key       = "neon_test_key_aaaaaaaaaaaaaaaaaaaa"
neon_region_id     = "aws-us-east-2"
neon_database_name = "agent_app"

# Cloudflare — fake but well-formed.
cloudflare_api_token  = "cf_test_token_aaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
cloudflare_account_id = "00000000000000000000000000000001"
cloudflare_zone_id    = "00000000000000000000000000000002"

# WorkOS public config
workos_client_id = "client_test_fake_id"

# Secret-manager seed values — placeholder strings, not real keys.
workos_api_key      = "sk_test_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE"
openai_api_key      = "sk-fake-openai-test-key"
anthropic_api_key   = "sk-ant-fake-anthropic-test-key"
langfuse_public_key = "pk-lf-fake-public-key"
langfuse_secret_key = "sk-lf-fake-secret-key"
mem0_api_key        = "m0-fake-mem0-key"
