#!/bin/bash

# Docker Image Size Analysis Script
# This script builds different versions of the Docker image and compares sizes

set -e

PROJECT_NAME="astroyaar-backend"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "🐳 Docker Image Size Analysis for $PROJECT_NAME"
echo "=================================================="

# Function to build and analyze image
build_and_analyze() {
    local dockerfile=$1
    local tag_suffix=$2
    local description=$3
    
    echo ""
    echo "📦 Building $description..."
    echo "Dockerfile: $dockerfile"
    
    # Build the image
    docker build -f $dockerfile -t ${PROJECT_NAME}:${tag_suffix} .
    
    # Get image size
    local size=$(docker images ${PROJECT_NAME}:${tag_suffix} --format "table {{.Size}}" | tail -n 1)
    local size_bytes=$(docker inspect ${PROJECT_NAME}:${tag_suffix} --format='{{.Size}}')
    local size_mb=$((size_bytes / 1024 / 1024))
    
    echo "✅ Built: ${PROJECT_NAME}:${tag_suffix}"
    echo "📏 Size: $size (${size_mb} MB)"
    
    # Store results
    echo "${tag_suffix},${description},${size},${size_mb}" >> /tmp/docker_sizes_${TIMESTAMP}.csv
}

# Initialize CSV file
echo "tag,description,size_human,size_mb" > /tmp/docker_sizes_${TIMESTAMP}.csv

# Build different versions
echo "🔨 Building different Docker image variants..."

# Original Dockerfile (if exists)
if [ -f "Dockerfile.original" ]; then
    build_and_analyze "Dockerfile.original" "original" "Original Dockerfile"
fi

# Current optimized Dockerfile
build_and_analyze "Dockerfile" "optimized" "Multi-stage Optimized (Debian Slim)"

# Ultra-slim Alpine version
build_and_analyze "Dockerfile.slim" "alpine" "Ultra-slim Alpine"

# Development version
build_and_analyze "Dockerfile.dev" "dev" "Development Version"

echo ""
echo "📊 Size Comparison Results:"
echo "=========================="

# Display results in a nice table
column -t -s ',' /tmp/docker_sizes_${TIMESTAMP}.csv

echo ""
echo "💾 Detailed Analysis:"
echo "===================="

# Get detailed breakdown of the optimized image
echo ""
echo "🔍 Layer analysis for optimized image:"
docker history ${PROJECT_NAME}:optimized --format "table {{.CreatedBy}}\t{{.Size}}" | head -20

echo ""
echo "📈 Size Reduction Analysis:"
echo "=========================="

# Calculate size differences
original_size=$(grep "original" /tmp/docker_sizes_${TIMESTAMP}.csv 2>/dev/null | cut -d',' -f4 || echo "0")
optimized_size=$(grep "optimized" /tmp/docker_sizes_${TIMESTAMP}.csv | cut -d',' -f4)
alpine_size=$(grep "alpine" /tmp/docker_sizes_${TIMESTAMP}.csv | cut -d',' -f4)

if [ "$original_size" != "0" ]; then
    reduction=$((original_size - optimized_size))
    percentage=$(( (reduction * 100) / original_size ))
    echo "🎯 Multi-stage optimization: ${reduction}MB reduction (${percentage}%)"
fi

alpine_reduction=$((optimized_size - alpine_size))
alpine_percentage=$(( (alpine_reduction * 100) / optimized_size ))
echo "🏔️  Alpine optimization: ${alpine_reduction}MB additional reduction (${alpine_percentage}%)"

echo ""
echo "💡 Recommendations:"
echo "=================="
echo "• Use 'Dockerfile.slim' for production (smallest size)"
echo "• Use 'Dockerfile' for production with Debian compatibility"
echo "• Use 'Dockerfile.dev' for development"
echo "• Consider removing unused dependencies from requirements.txt"
echo "• Use .dockerignore to exclude unnecessary files"

echo ""
echo "🚀 Next Steps:"
echo "=============="
echo "1. Test the Alpine image thoroughly (some packages may behave differently)"
echo "2. Update your CI/CD to use the optimized Dockerfile"
echo "3. Monitor application performance with smaller images"
echo "4. Consider using distroless images for even smaller size"

# Cleanup
echo ""
echo "🧹 Cleaning up temporary files..."
rm -f /tmp/docker_sizes_${TIMESTAMP}.csv

echo ""
echo "✅ Analysis complete! Choose the best image for your needs." 