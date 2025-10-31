# Custom CA Certificate Configuration for OpenShift

This guide shows how to configure the Weather Agent to use custom Certificate Authority (CA) bundles in enterprise OpenShift clusters, particularly those with FIPS mode enabled.

## Overview

Many enterprise OpenShift environments use internal or corporate Certificate Authorities for signing service certificates. The Weather Agent includes automatic SSL/TLS certificate verification with intelligent CA bundle selection:

1. **SSL_CERT_FILE environment variable** (highest priority)
2. **Service CA** (`/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt`)
3. **System CA bundle** (`/etc/pki/tls/certs/ca-bundle.crt`)

## When You Need Custom CA Configuration

You need custom CA configuration when your environment has:

- Internal services using certificates signed by a corporate CA
- Custom certificate authorities not included in standard trust bundles
- Self-signed certificates in development/testing environments
- Certificate chains that aren't in the default service CA or system bundle

This is a common setup in enterprise environments where security policies require internal CAs.

## Prerequisites

Before starting, you need:

- Your organization's root CA certificate (usually provided by your platform team)
- Appropriate permissions to create ConfigMaps in your namespace
- Access to modify deployment manifests

## Step-by-Step Implementation

### Step 1: Create Custom CA ConfigMap

Create a ConfigMap containing your CA certificate. The certificate should be in PEM format.

```bash
# Create ConfigMap from your CA certificate file
oc create configmap custom-ca-bundle \
  --from-file=ca-bundle.crt=/path/to/your-ca-certificate.crt \
  -n your-namespace
```

**Example with corporate CA:**

```bash
# If your CA is in a file called corporate-root-ca.crt
oc create configmap custom-ca-bundle \
  --from-file=ca-bundle.crt=corporate-root-ca.crt \
  -n weather-agent
```

**If your CA already exists in another namespace:**

```bash
# Copy from openshift-config namespace (common location)
oc get configmap corporate-ca-bundle -n openshift-config -o yaml | \
  sed 's/namespace: openshift-config/namespace: your-namespace/' | \
  oc apply -f -

# Rename if needed
oc get configmap corporate-ca-bundle -n your-namespace -o yaml | \
  sed 's/name: corporate-ca-bundle/name: custom-ca-bundle/' | \
  oc apply -f -
```

**Verify the ConfigMap was created:**

```bash
oc get configmap custom-ca-bundle -n your-namespace
oc describe configmap custom-ca-bundle -n your-namespace
```

### Step 2: Update Deployment Manifest

Add the custom CA volume mount and environment variable to `manifests/openshift/api/deployment.yaml`:

#### 2a. Add Environment Variable

Find the `env:` section (around line 42-118) and add:

```yaml
        # Custom CA configuration
        - name: SSL_CERT_FILE
          value: /etc/pki/ca-trust/source/anchors/custom-ca.crt
```

**Complete environment variable section should look like:**

```yaml
        env:
        # ... existing env vars ...
        - name: API_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: weather-agent-secrets
              key: API_SECRET_KEY
        # Custom CA configuration
        - name: SSL_CERT_FILE
          value: /etc/pki/ca-trust/source/anchors/custom-ca.crt
        resources:
```

#### 2b. Add Volume Mount

Find the `volumeMounts:` section (around line 156) and add:

```yaml
        volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: custom-ca
          mountPath: /etc/pki/ca-trust/source/anchors/custom-ca.crt
          subPath: ca-bundle.crt
          readOnly: true
```

#### 2c. Add Volume Definition

Find the `volumes:` section (around line 159) and add:

```yaml
      volumes:
      - name: tmp
        emptyDir: {}
      - name: custom-ca
        configMap:
          name: custom-ca-bundle
          items:
          - key: ca-bundle.crt
            path: ca-bundle.crt
```

### Step 3: Apply the Changes

```bash
# Apply updated deployment
oc apply -f manifests/openshift/api/deployment.yaml -n your-namespace

# Wait for rollout to complete
oc rollout status deployment/weather-agent-api -n your-namespace
```

### Step 4: Verify the Configuration

Run these verification commands to ensure the custom CA is properly configured:

```bash
# 1. Check environment variable is set
oc exec deployment/weather-agent-api -n your-namespace -- \
  env | grep SSL_CERT_FILE

# Expected output:
# SSL_CERT_FILE=/etc/pki/ca-trust/source/anchors/custom-ca.crt

# 2. Verify CA file is mounted
oc exec deployment/weather-agent-api -n your-namespace -- \
  ls -la /etc/pki/ca-trust/source/anchors/custom-ca.crt

# Expected output:
# -rw-r--r--. 1 root 1000820000 [size] [date] /etc/pki/ca-trust/source/anchors/custom-ca.crt

# 3. Check CA certificate content
oc exec deployment/weather-agent-api -n your-namespace -- \
  head -5 /etc/pki/ca-trust/source/anchors/custom-ca.crt

# Expected output:
# -----BEGIN CERTIFICATE-----
# [certificate content]

# 4. Verify certificate details
oc exec deployment/weather-agent-api -n your-namespace -- \
  openssl x509 -in /etc/pki/ca-trust/source/anchors/custom-ca.crt \
  -noout -subject -issuer

# 5. Check MCP connection in logs
oc logs deployment/weather-agent-api -n your-namespace --tail=50 | \
  grep -E "(MCP|connected)"

# Expected output:
# Agent 'WeatherAgent' connected to MCP with 3 tools
# Weather agent initialized with MCP server

# 6. Test API health endpoint
ROUTE=$(oc get route weather-agent-api -n your-namespace -o jsonpath='{.spec.host}')
curl https://${ROUTE}/health | jq '{mcp_connected, status}'

# Expected output:
# {
#   "mcp_connected": true,
#   "status": "healthy"
# }
```

## Complete Working Example

Here's a complete working configuration that has been tested in production:

### deployment.yaml (relevant sections)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: weather-agent-api
spec:
  template:
    spec:
      containers:
      - name: weather-agent-api
        image: image-registry.openshift-image-registry.svc:5000/weather-agent/weather-agent-api:latest
        env:
        # ... other environment variables ...
        - name: API_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: weather-agent-secrets
              key: API_SECRET_KEY
        # Custom CA configuration
        - name: SSL_CERT_FILE
          value: /etc/pki/ca-trust/source/anchors/custom-ca.crt

        volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: custom-ca
          mountPath: /etc/pki/ca-trust/source/anchors/custom-ca.crt
          subPath: ca-bundle.crt
          readOnly: true

      volumes:
      - name: tmp
        emptyDir: {}
      - name: custom-ca
        configMap:
          name: custom-ca-bundle
          items:
          - key: ca-bundle.crt
            path: ca-bundle.crt
```

### Commands summary

```bash
# 1. Create ConfigMap with your CA certificate
oc create configmap custom-ca-bundle \
  --from-file=ca-bundle.crt=/path/to/your-ca-certificate.crt \
  -n your-namespace

# 2. Apply deployment changes
oc apply -f manifests/openshift/api/deployment.yaml -n your-namespace

# 3. Verify deployment
oc rollout status deployment/weather-agent-api -n your-namespace
```

## Troubleshooting

### Issue: Certificate verify failed

**Symptom:**

```text
Failed to connect to MCP server: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Solutions:**

1. **Verify CA file contains the correct certificate:**

   ```bash
   oc exec deployment/weather-agent-api -n your-namespace -- \
     openssl x509 -in /etc/pki/ca-trust/source/anchors/custom-ca.crt \
     -text -noout | head -20
   ```

2. **Check if CA matches the server certificate:**

   ```bash
   # Get server certificate issuer
   echo | openssl s_client -connect your-mcp-server:443 -showcerts 2>/dev/null | \
     openssl x509 -noout -issuer

   # Compare with your CA certificate subject
   oc exec deployment/weather-agent-api -n your-namespace -- \
     openssl x509 -in /etc/pki/ca-trust/source/anchors/custom-ca.crt \
     -noout -subject
   ```

3. **Verify environment variable is set:**

   ```bash
   oc exec deployment/weather-agent-api -n your-namespace -- \
     env | grep SSL_CERT_FILE
   ```

4. **Check the CA bundle includes the full certificate chain:**
   - Your CA file may need to include intermediate certificates
   - Try including the full chain: root CA + intermediate CAs
   - Contact your platform team if you need the complete chain

### Issue: File not found

**Symptom:**

```text
FileNotFoundError: [Errno 2] No such file or directory: '/etc/pki/ca-trust/source/anchors/custom-ca.crt'
```

**Solutions:**

1. **Verify ConfigMap exists:**

   ```bash
   oc get configmap custom-ca-bundle -n your-namespace
   ```

2. **Check volume mount in pod:**

   ```bash
   oc get pod -l app=weather-agent,component=api -n your-namespace \
     -o jsonpath='{.items[0].spec.volumes}' | jq
   ```

3. **Verify deployment YAML is applied:**

   ```bash
   oc get deployment weather-agent-api -n your-namespace -o yaml | \
     grep -A 10 "volumeMounts:"
   ```

### Issue: ConfigMap changes not reflected

**Symptom:**
Old certificate still being used after updating ConfigMap

**Solution:**
Restart the deployment to pick up ConfigMap changes:

```bash
oc rollout restart deployment/weather-agent-api -n your-namespace
```

Note: ConfigMap updates are eventually consistent but may take time to propagate to running pods.

## Alternative Configurations

### Using System CA Bundle

If your organization's CA is already included in the Red Hat UBI system bundle:

```yaml
env:
  # Use system bundle (includes most public CAs and may include enterprise CAs)
  - name: SSL_CERT_FILE
    value: /etc/pki/tls/certs/ca-bundle.crt
```

### Using Service CA

For connecting to services within the same OpenShift cluster:

```yaml
env:
  # Use OpenShift service CA (for internal *.svc.cluster.local services)
  - name: SSL_CERT_FILE
    value: /var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt
```

### No Configuration Needed

If you don't set `SSL_CERT_FILE`, the agent automatically:

1. Tries the service CA first (if the file exists)
2. Falls back to the system CA bundle

This works for most standard OpenShift deployments.

## FIPS Compliance Notes

✅ **This configuration is FIPS-compliant** because:

- Uses standard CA bundle verification (doesn't disable SSL)
- Uses system-provided cryptography libraries
- No weak ciphers or deprecated algorithms
- Follows Red Hat UBI9 FIPS guidelines

❌ **NOT FIPS-compliant alternatives:**

- Setting `verify=False` (disables all SSL verification)
- Using self-signed certificates without proper CA trust chain
- Disabling certificate validation in code

## Production Best Practices

1. **Use proper CA certificates** - Never disable SSL verification in production
2. **Test in development first** - Verify configuration in non-production before deploying
3. **Document your CA source** - Record where the certificate came from and who maintains it
4. **Plan for certificate rotation** - CAs expire and need renewal (typically 5-10 years)
5. **Use namespaced ConfigMaps** - Don't share CA bundles across unrelated applications
6. **Audit access controls** - Restrict who can modify CA ConfigMaps
7. **Monitor certificate expiration** - Set up alerts well before expiration (90+ days)
8. **Maintain certificate chain** - Ensure intermediate CAs are included if required

## Getting Your CA Certificate

If you need to obtain your organization's CA certificate:

**Ask your platform team:**

> "What CA certificate should applications trust for internal HTTPS connections?"

They will provide either:

- A certificate file (`.crt`, `.pem`, or `.cer` format)
- A ConfigMap name and namespace where it's stored
- Instructions to use the service CA or system bundle

**Common locations in OpenShift:**

```bash
# Check for cluster-wide CA bundles
oc get configmap -n openshift-config | grep -i ca

# Check proxy configuration
oc get proxy cluster -o yaml | grep trustedCA
```

## See Also

- [README-OPENSHIFT.md](../README-OPENSHIFT.md) - OpenShift deployment guide
- [CLAUDE.md](../CLAUDE.md) - Development patterns and architecture
- [OpenShift Security Context Constraints](https://docs.openshift.com/container-platform/latest/authentication/managing-security-context-constraints.html)
- [Red Hat UBI FIPS Mode](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/security_hardening/using-the-system-wide-cryptographic-policies_security-hardening)
- [OpenShift Certificate Management](https://docs.openshift.com/container-platform/latest/security/certificates/replacing-default-ingress-certificate.html)
