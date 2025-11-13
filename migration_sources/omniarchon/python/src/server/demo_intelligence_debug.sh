#!/bin/bash
# Intelligence Debug Demo Script
#
# This script demonstrates how to use the intelligence debugging tools
# for various scenarios and troubleshooting workflows.

set -e  # Exit on any error

echo "🎯 ARCHON INTELLIGENCE DEBUG DEMONSTRATION"
echo "============================================="

echo ""
echo "1️⃣  FIXTURE TESTING (No API Required)"
echo "--------------------------------------------"
echo "📋 Testing fixture generation and validation..."
python test_fixtures.py

echo ""
echo "📊 Showing fixture dashboard..."
python debug_intelligence.py --fixture-dashboard

echo ""
echo "2️⃣  SIMULATED DEBUGGING WORKFLOW"
echo "--------------------------------------------"
echo ""
echo "🔍 This is what you would run to debug correlation issues:"
echo ""
echo "# Step 1: Test live API endpoints"
echo "python debug_intelligence.py --live-api"
echo ""
echo "# Step 2: Validate data quality"
echo "python debug_intelligence.py --validate"
echo ""
echo "# Step 3: Compare with expected fixture data"
echo "python debug_intelligence.py --compare-data"
echo ""
echo "# Step 4: If quality is poor, force regenerate"
echo "python debug_intelligence.py --force-regenerate"
echo ""
echo "# Step 5: Run comprehensive test and save results"
echo "python debug_intelligence.py --comprehensive"

echo ""
echo "3️⃣  USAGE EXAMPLES BY SCENARIO"
echo "--------------------------------------------"
echo ""
echo "🔧 Common debugging scenarios:"
echo ""
echo "A) Dashboard shows 'Tech: Unknown'"
echo "   → python debug_intelligence.py --validate"
echo "   → python debug_intelligence.py --force-regenerate"
echo ""
echo "B) No correlation data in API"
echo "   → python debug_intelligence.py --live-api"
echo "   → python debug_intelligence.py --regenerate"
echo ""
echo "C) Want to see what good data looks like"
echo "   → python debug_intelligence.py --fixture-dashboard"
echo "   → python debug_intelligence.py --compare-data"
echo ""
echo "D) After changing correlation algorithms"
echo "   → python debug_intelligence.py --force-regenerate"
echo "   → python debug_intelligence.py --comprehensive"

echo ""
echo "4️⃣  FILE STRUCTURE OVERVIEW"
echo "--------------------------------------------"
echo "📁 Debug tool files:"
ls -la | grep -E "(debug|fixture|test)" | grep -v ".pyc"

echo ""
echo "5️⃣  HELP AND DOCUMENTATION"
echo "--------------------------------------------"
echo "📖 For detailed usage instructions:"
echo "   → cat INTELLIGENCE_DEBUG_GUIDE.md"
echo ""
echo "🆘 For command help:"
echo "   → python debug_intelligence.py --help"

echo ""
echo "✅ Demo completed! The debugging tools are ready to use."
echo "💡 Start with: python debug_intelligence.py --fixture-dashboard"
