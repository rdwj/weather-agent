#!/bin/bash

# Weather Agent OpenShift Deployment Script
# This script deploys the Weather Agent application to OpenShift

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="${NAMESPACE:-weather-agent}"
REGISTRY="${REGISTRY:-image-registry.openshift-image-registry.svc:5000}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Function to print colored messages
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check if logged in to OpenShift
check_oc_login() {
    if ! oc whoami &>/dev/null; then
        print_message "$RED" "❌ Not logged in to OpenShift"
        print_message "$YELLOW" "Please login using: oc login <your-cluster-url>"
        exit 1
    fi
    print_message "$GREEN" "✅ Logged in as: $(oc whoami)"
}

# Function to create namespace if it doesn't exist
setup_namespace() {
    if oc get namespace "$NAMESPACE" &>/dev/null; then
        print_message "$YELLOW" "ℹ️  Namespace $NAMESPACE already exists"
    else
        print_message "$BLUE" "Creating namespace: $NAMESPACE"
        oc new-project "$NAMESPACE" --display-name="Weather Agent" \
            --description="Intelligent Weather Assistant with MCP Integration"
    fi

    # Ensure we're using the correct namespace
    oc project "$NAMESPACE"
}

# Function to create secrets
create_secrets() {
    print_message "$BLUE" "📝 Setting up secrets..."

    # Check if secret already exists in cluster
    if oc get secret weather-agent-secrets -n "$NAMESPACE" &>/dev/null; then
        print_message "$YELLOW" "ℹ️  Secrets already exist."
        read -p "Do you want to update them from .env? (y/n): " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if [ -f "scripts/apply-secret.sh" ]; then
                print_message "$BLUE" "Updating secrets from .env file..."
                ./scripts/apply-secret.sh
            else
                print_message "$RED" "❌ apply-secret.sh script not found!"
                exit 1
            fi
        else
            print_message "$YELLOW" "Keeping existing secrets"
        fi
    else
        # Create new secret from .env
        if [ -f "scripts/apply-secret.sh" ]; then
            print_message "$BLUE" "Creating secrets from .env file..."
            ./scripts/apply-secret.sh
        else
            print_message "$RED" "❌ apply-secret.sh script not found!"
            exit 1
        fi
    fi
}

# Function to deploy common resources
deploy_common() {
    print_message "$BLUE" "🚀 Deploying common resources..."

    # Deploy ConfigMap
    oc apply -f manifests/openshift/common/configmap.yaml -n "$NAMESPACE"
    print_message "$GREEN" "✅ ConfigMap deployed"
}

# Function to deploy Redis
deploy_redis() {
    print_message "$BLUE" "🗄️  Deploying Redis cache..."

    # Delete existing deployment if it exists (to avoid selector conflicts)
    if oc get deployment weather-agent-redis -n "$NAMESPACE" &>/dev/null; then
        print_message "$YELLOW" "Removing existing Redis deployment..."
        oc delete deployment weather-agent-redis -n "$NAMESPACE"
        sleep 5
    fi

    oc apply -f manifests/openshift/redis/deployment.yaml -n "$NAMESPACE"

    # Wait for Redis to be ready
    print_message "$YELLOW" "⏳ Waiting for Redis to be ready..."
    oc rollout status deployment/weather-agent-redis -n "$NAMESPACE" --timeout=300s
    print_message "$GREEN" "✅ Redis deployed and ready"
}

# Function to build and push container image
build_and_push() {
    print_message "$BLUE" "🔨 Building container image..."

    # Check if using OpenShift internal registry
    if [[ "$REGISTRY" == *"openshift-image-registry"* ]]; then
        # Build using BuildConfig in OpenShift
        print_message "$BLUE" "Using OpenShift BuildConfig..."

        # Create BuildConfig if it doesn't exist (use Containerfile.prod)
        if ! oc get buildconfig weather-agent -n "$NAMESPACE" &>/dev/null; then
            oc new-build --binary --name=weather-agent \
                --strategy=docker \
                --docker-image=registry.access.redhat.com/ubi9/python-311:latest \
                -n "$NAMESPACE"
        fi

        # Start build with the production Containerfile
        oc start-build weather-agent --from-dir=. --follow \
            --build-arg-file=Containerfile.prod \
            -n "$NAMESPACE"

        # Tag for API and UI
        oc tag weather-agent:latest weather-agent-api:latest -n "$NAMESPACE"
        oc tag weather-agent:latest weather-agent-ui:latest -n "$NAMESPACE"
    else
        # Build locally and push
        print_message "$BLUE" "Building with Podman..."

        # Build image
        podman build --platform linux/amd64 \
            -t "$REGISTRY/$NAMESPACE/weather-agent:$IMAGE_TAG" \
            -f Containerfile.prod . --no-cache

        # Push to registry
        podman push "$REGISTRY/$NAMESPACE/weather-agent:$IMAGE_TAG"

        # Tag for API and UI
        podman tag "$REGISTRY/$NAMESPACE/weather-agent:$IMAGE_TAG" \
            "$REGISTRY/$NAMESPACE/weather-agent-api:$IMAGE_TAG"
        podman tag "$REGISTRY/$NAMESPACE/weather-agent:$IMAGE_TAG" \
            "$REGISTRY/$NAMESPACE/weather-agent-ui:$IMAGE_TAG"

        podman push "$REGISTRY/$NAMESPACE/weather-agent-api:$IMAGE_TAG"
        podman push "$REGISTRY/$NAMESPACE/weather-agent-ui:$IMAGE_TAG"
    fi

    print_message "$GREEN" "✅ Container image built and pushed"
}

# Function to deploy API
deploy_api() {
    print_message "$BLUE" "🌐 Deploying Weather Agent API..."

    # Delete existing deployment if it exists (to avoid selector conflicts)
    if oc get deployment weather-agent-api -n "$NAMESPACE" &>/dev/null; then
        print_message "$YELLOW" "Removing existing API deployment..."
        oc delete deployment weather-agent-api -n "$NAMESPACE"
        sleep 5
    fi

    oc apply -f manifests/openshift/api/deployment.yaml -n "$NAMESPACE"

    # Wait for deployment
    print_message "$YELLOW" "⏳ Waiting for API to be ready..."
    oc rollout status deployment/weather-agent-api -n "$NAMESPACE" --timeout=300s

    # Get route
    API_ROUTE=$(oc get route weather-agent-api -n "$NAMESPACE" -o jsonpath='{.spec.host}')
    print_message "$GREEN" "✅ API deployed: https://$API_ROUTE"
}

# Function to deploy UI
deploy_ui() {
    print_message "$BLUE" "💻 Deploying Weather Agent UI..."

    # Delete existing deployment if it exists (to avoid selector conflicts)
    if oc get deployment weather-agent-ui -n "$NAMESPACE" &>/dev/null; then
        print_message "$YELLOW" "Removing existing UI deployment..."
        oc delete deployment weather-agent-ui -n "$NAMESPACE"
        sleep 5
    fi

    oc apply -f manifests/openshift/ui/deployment.yaml -n "$NAMESPACE"

    # Wait for deployment
    print_message "$YELLOW" "⏳ Waiting for UI to be ready..."
    oc rollout status deployment/weather-agent-ui -n "$NAMESPACE" --timeout=300s

    # Get route
    UI_ROUTE=$(oc get route weather-agent-ui -n "$NAMESPACE" -o jsonpath='{.spec.host}')
    print_message "$GREEN" "✅ UI deployed: https://$UI_ROUTE"
}

# Function to check deployment status
check_status() {
    print_message "$BLUE" "📊 Checking deployment status..."
    echo ""

    print_message "$BLUE" "Pods:"
    oc get pods -n "$NAMESPACE" -l app=weather-agent
    echo ""

    print_message "$BLUE" "Services:"
    oc get svc -n "$NAMESPACE" -l app=weather-agent
    echo ""

    print_message "$BLUE" "Routes:"
    oc get routes -n "$NAMESPACE" -l app=weather-agent
}

# Function to run smoke tests
run_tests() {
    print_message "$BLUE" "🧪 Running smoke tests..."

    # Get API route
    API_ROUTE=$(oc get route weather-agent-api -n "$NAMESPACE" -o jsonpath='{.spec.host}')

    # Test health endpoint
    print_message "$YELLOW" "Testing API health..."
    if curl -s "https://$API_ROUTE/health" | grep -q "healthy"; then
        print_message "$GREEN" "✅ API health check passed"
    else
        print_message "$RED" "❌ API health check failed"
    fi

    # Test UI
    UI_ROUTE=$(oc get route weather-agent-ui -n "$NAMESPACE" -o jsonpath='{.spec.host}')
    print_message "$YELLOW" "Testing UI..."
    if curl -s -o /dev/null -w "%{http_code}" "https://$UI_ROUTE" | grep -q "200\|302"; then
        print_message "$GREEN" "✅ UI is accessible"
    else
        print_message "$RED" "❌ UI is not accessible"
    fi
}

# Pre-deployment checklist
pre_deployment_checklist() {
    print_message "$BLUE" "📋 Pre-Deployment Checklist"
    print_message "$BLUE" "=========================="
    echo ""

    local ready=true

    # Check .env file
    if [ -f ".env" ]; then
        print_message "$GREEN" "✅ .env file found"

        # Check required variables
        source .env
        if [ -z "$LLM_URL" ]; then
            print_message "$RED" "❌ LLM_URL not set in .env"
            ready=false
        else
            print_message "$GREEN" "✅ LLM_URL configured"
        fi

        if [ -z "$LLM_API_KEY" ]; then
            print_message "$RED" "❌ LLM_API_KEY not set in .env"
            ready=false
        else
            print_message "$GREEN" "✅ LLM_API_KEY configured"
        fi

        if [ -z "$LLM_MODEL_NAME" ]; then
            print_message "$RED" "❌ LLM_MODEL_NAME not set in .env"
            ready=false
        else
            print_message "$GREEN" "✅ LLM_MODEL_NAME configured"
        fi
    else
        print_message "$RED" "❌ .env file not found"
        print_message "$YELLOW" "   Copy .env.example to .env and configure it"
        ready=false
    fi

    # Check manifests
    if [ -d "manifests/openshift" ]; then
        print_message "$GREEN" "✅ OpenShift manifests found"
    else
        print_message "$RED" "❌ OpenShift manifests not found"
        ready=false
    fi

    # Check scripts
    if [ -f "scripts/apply-secret.sh" ]; then
        print_message "$GREEN" "✅ Secret application script found"
    else
        print_message "$RED" "❌ Secret application script not found"
        ready=false
    fi

    # Check Containerfile
    if [ -f "Containerfile.prod" ] || [ -f "Containerfile" ]; then
        print_message "$GREEN" "✅ Containerfile found"
    else
        print_message "$RED" "❌ Containerfile not found"
        ready=false
    fi

    echo ""
    if [ "$ready" = false ]; then
        print_message "$RED" "❌ Pre-deployment checks failed"
        print_message "$YELLOW" "Please fix the issues above and try again"
        return 1
    else
        print_message "$GREEN" "✅ All pre-deployment checks passed"
        echo ""
        return 0
    fi
}

# Main deployment flow
main() {
    print_message "$BLUE" "🚀 Weather Agent OpenShift Deployment"
    print_message "$BLUE" "====================================="
    echo ""

    # Run pre-deployment checklist
    if ! pre_deployment_checklist; then
        exit 1
    fi

    # Check prerequisites
    check_oc_login

    # Setup namespace
    setup_namespace

    # Ask about build
    read -p "Do you want to build and push the container image? (y/n): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        build_and_push
    fi

    # Deploy components
    create_secrets
    deploy_common
    deploy_redis
    deploy_api
    deploy_ui

    # Check status
    echo ""
    check_status

    # Run tests
    echo ""
    run_tests

    # Summary
    echo ""
    print_message "$GREEN" "✨ Deployment Complete!"
    print_message "$GREEN" "========================"

    API_ROUTE=$(oc get route weather-agent-api -n "$NAMESPACE" -o jsonpath='{.spec.host}')
    UI_ROUTE=$(oc get route weather-agent-ui -n "$NAMESPACE" -o jsonpath='{.spec.host}')

    print_message "$GREEN" "📍 API URL: https://$API_ROUTE"
    print_message "$GREEN" "🌐 UI URL: https://$UI_ROUTE"
    print_message "$GREEN" ""
    print_message "$YELLOW" "Next steps:"
    print_message "$YELLOW" "1. Visit the UI URL to use the Weather Assistant"
    print_message "$YELLOW" "2. Check API docs at: https://$API_ROUTE/docs"
    print_message "$YELLOW" "3. Monitor logs: oc logs -f deployment/weather-agent-api -n $NAMESPACE"
}

# Run main function
main "$@"