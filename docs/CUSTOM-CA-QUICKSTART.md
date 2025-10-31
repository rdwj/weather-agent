# Custom CA Configuration - Quick Start

## Overview

This quick start guide shows how to configure the Weather Agent for enterprise OpenShift environments that use internal Certificate Authorities. This is a common setup in organizations with strict security policies.

**When you need this:** Your organization uses internal/corporate CAs to sign service certificates, and your MCP server or other services use these certificates.

**What's included:** The Weather Agent already has intelligent SSL verification built-in. This guide shows how to point it to your specific CA bundle.

## What's Already Implemented

### Code (Already in the Repository)

**File:** `src/core/base_agent.py` (lines 213-233)

The agent automatically selects the right CA bundle:

1. Checks `SSL_CERT_FILE` environment variable (if you set one)
2. Falls back to service CA (`/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt`)
3. Falls back to system bundle (`/etc/pki/tls/certs/ca-bundle.crt`)

**You don't need to modify any code.** The SSL verification is already implemented and working.

### What You Need to Configure

Only **deployment configuration** (if you need a custom CA):

1. Create a ConfigMap with your CA certificate
2. Mount it as a volume in the deployment
3. Set environment variable to point to it

## Quick Implementation (3 Steps)

### Step 1: Create ConfigMap with Your CA

```bash
# Replace /path/to/your-ca.crt with your actual CA certificate file
oc create configmap custom-ca-bundle \
  --from-file=ca-bundle.crt=/path/to/your-ca.crt \
  -n your-namespace
```

### Step 2: Update deployment.yaml

Add these three sections to `manifests/openshift/api/deployment.yaml`:

**a) Environment Variable** (add around line 119, after API_SECRET_KEY):

```yaml
        # Custom CA configuration
        - name: SSL_CERT_FILE
          value: /etc/pki/ca-trust/source/anchors/custom-ca.crt
```

**b) Volume Mount** (add around line 159, after tmp mount):

```yaml
        - name: custom-ca
          mountPath: /etc/pki/ca-trust/source/anchors/custom-ca.crt
          subPath: ca-bundle.crt
          readOnly: true
```

**c) Volume Definition** (add around line 166, after tmp volume):

```yaml
      - name: custom-ca
        configMap:
          name: custom-ca-bundle
          items:
          - key: ca-bundle.crt
            path: ca-bundle.crt
```

### Step 3: Apply and Verify

```bash
# Apply the updated deployment
oc apply -f manifests/openshift/api/deployment.yaml -n your-namespace

# Wait for rollout
oc rollout status deployment/weather-agent-api -n your-namespace

# Verify it worked
oc logs deployment/weather-agent-api -n your-namespace --tail=50 | \
  grep "connected to MCP"
```

## Verification Commands

```bash
# 1. Check environment variable is set
oc exec deployment/weather-agent-api -n your-namespace -- \
  env | grep SSL_CERT_FILE

# 2. Verify CA file is mounted
oc exec deployment/weather-agent-api -n your-namespace -- \
  ls -la /etc/pki/ca-trust/source/anchors/custom-ca.crt

# 3. Check MCP connection
oc logs deployment/weather-agent-api -n your-namespace --tail=50 | \
  grep "connected to MCP"

# Expected: "Agent 'WeatherAgent' connected to MCP with 3 tools"

# 4. Test API health
ROUTE=$(oc get route weather-agent-api -n your-namespace -o jsonpath='{.spec.host}')
curl https://${ROUTE}/health | jq '{mcp_connected, status}'

# Expected: {"mcp_connected": true, "status": "healthy"}
```

## Production-Tested Configuration

This configuration has been tested and verified on FIPS-enabled OpenShift clusters:

✅ **ConfigMap created** - CA bundle stored securely
✅ **Deployment updated** - Volume mount and env var configured
✅ **MCP connection** - Successfully connected using custom CA
✅ **API tested** - All endpoints working
✅ **FIPS compliant** - Uses standard SSL verification

## How It Works

The combination of all pieces makes this work:

| Component | Purpose |
|-----------|---------|
| **Code** (already implemented) | Reads SSL_CERT_FILE and passes CA path to httpx |
| **ConfigMap** | Provides the CA certificate file |
| **Volume mount** | Makes the file available inside the pod |
| **Environment variable** | Tells the code which file to use |

**All four pieces are required.** The code change in `base_agent.py` is what makes httpx trust your CA - without it, just mounting a ConfigMap won't work.

## Common Scenarios

### Scenario 1: No Custom CA Needed (Default)

Your environment uses standard OpenShift service CAs or public CAs.

**Action:** Nothing! The agent automatically uses the service CA or system bundle.

### Scenario 2: Corporate CA Required

Your organization has an internal CA that signs service certificates.

**Action:** Follow the 3-step quick implementation above.

### Scenario 3: CA Already in Another Namespace

Your platform team maintains a cluster-wide CA ConfigMap.

**Action:**

```bash
# Copy from openshift-config to your namespace
oc get configmap corporate-ca -n openshift-config -o yaml | \
  sed 's/namespace: openshift-config/namespace: your-namespace/' | \
  oc apply -f -

# Rename if needed
oc patch configmap corporate-ca -n your-namespace \
  --type merge -p '{"metadata":{"name":"custom-ca-bundle"}}'
```

Then proceed with Step 2 and 3 from the quick implementation.

## Troubleshooting Quick Reference

| Symptom | Solution |
|---------|----------|
| `CERTIFICATE_VERIFY_FAILED` | Verify CA matches server cert: `openssl x509 -in /etc/pki/ca-trust/source/anchors/custom-ca.crt -noout -subject` |
| `File not found` | Check ConfigMap exists: `oc get configmap custom-ca-bundle -n your-namespace` |
| ConfigMap update not working | Restart deployment: `oc rollout restart deployment/weather-agent-api -n your-namespace` |
| Can't find CA certificate | Ask platform team: "What CA should apps trust for internal HTTPS?" |

## Getting Your CA Certificate

**Don't have your CA certificate yet?**

Ask your OpenShift platform team:

> "What CA certificate should applications trust for internal HTTPS connections?"

They'll provide either:

- A certificate file (`.crt`, `.pem`, or `.cer`)
- A ConfigMap name and namespace where it's stored
- Confirmation that you should use the service CA or system bundle

**Common locations to check:**

```bash
# Cluster-wide CAs
oc get configmap -n openshift-config | grep -i ca

# Proxy configuration
oc get proxy cluster -o yaml | grep trustedCA
```

## Key Points

✅ **Code is already done** - SSL verification implemented in base_agent.py
✅ **FIPS compliant** - Uses standard cryptography, no security shortcuts
✅ **Production tested** - Verified on real FIPS-enabled clusters
✅ **Auto-fallback** - Works without config in standard environments
✅ **Flexible** - Supports custom CAs when needed

## Next Steps

1. **Determine if you need custom CA** - Check with your platform team
2. **Get your CA certificate** - From platform team or existing ConfigMap
3. **Follow 3-step implementation** - ConfigMap → deployment.yaml → apply
4. **Verify it works** - Use verification commands above
5. **Refer to full docs if needed** - See `docs/CUSTOM-CA-CONFIGURATION.md`

## Documentation

- **Complete guide:** `docs/CUSTOM-CA-CONFIGURATION.md` - Full details, troubleshooting, examples
- **Deployment guide:** `README-OPENSHIFT.md` - OpenShift deployment process
- **Architecture:** `CLAUDE.md` - How the agent works internally

## Quick FAQ

**Q: Do I need to change the code?**
A: No! SSL verification is already implemented.

**Q: What if I don't have a custom CA?**
A: Don't configure anything. The agent automatically uses service CA or system bundle.

**Q: Is this FIPS compliant?**
A: Yes! Uses standard SSL verification with system cryptography.

**Q: What if ConfigMap changes?**
A: Restart: `oc rollout restart deployment/weather-agent-api -n your-namespace`

**Q: Where's the code that does this?**
A: `src/core/base_agent.py` lines 213-233 - already implemented!
