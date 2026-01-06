"""
Evaluation Demo - Phase 4
==========================
This script demonstrates offline evaluation utilities:
1. Replaying logged queries
2. Comparing retrieval parameters
3. Analyzing parameter impact
4. Batch evaluation

Run this after main.py has generated some logs.
"""

from evaluation import (
    replay_logged_queries,
    compare_retrieval_parameters,
    analyze_parameter_impact,
    batch_evaluate,
    quick_test
)
from query_logger import print_log_summary, LogReader


def main():
    print("="*80)
    print("PHASE 4 EVALUATION DEMO")
    print("="*80)
    print()

    # Demo 1: Show log summary
    print("\n" + "="*80)
    print("DEMO 1: LOG SUMMARY")
    print("="*80)
    print_log_summary()

    # Demo 2: Quick test of a single query
    print("\n" + "="*80)
    print("DEMO 2: QUICK TEST")
    print("="*80)
    quick_test("What are the library hours?", show_chunks=True)

    # Demo 3: Compare retrieval parameters for a query
    print("\n" + "="*80)
    print("DEMO 3: PARAMETER COMPARISON")
    print("="*80)
    compare_retrieval_parameters(
        query="What IT services are available to students?",
        top_k_values=[2, 4, 6],
        threshold_values=[0.4, 0.5, 0.6]
    )

    # Demo 4: Analyze impact of top_k parameter
    print("\n" + "="*80)
    print("DEMO 4: PARAMETER IMPACT ANALYSIS")
    print("="*80)
    test_queries = [
        "What are the library hours?",
        "How much does parking cost?",
        "What dining options are available?",
        "Tell me about student employment"
    ]
    analyze_parameter_impact(
        queries=test_queries,
        parameter_name="top_k",
        parameter_values=[2, 4, 6, 8]
    )

    # Demo 5: Batch evaluation
    print("\n" + "="*80)
    print("DEMO 5: BATCH EVALUATION")
    print("="*80)
    batch_queries = [
        "What are the library hours?",
        "How much does parking cost?",
        "What meal plans are available?",
        "What IT services are available?",
        "Tell me about student employment opportunities",
        "What is the weather today?",  # Should have low confidence
    ]
    batch_evaluate(batch_queries, top_k=4, score_threshold=0.5, show_details=False)

    # Demo 6: Replay logged queries (if any exist)
    print("\n" + "="*80)
    print("DEMO 6: REPLAY LOGGED QUERIES")
    print("="*80)
    reader = LogReader()
    responses = reader.read_responses(limit=3)

    if responses:
        print(f"Found {len(responses)} logged queries. Replaying with different parameters...")
        replay_logged_queries(limit=3, top_k=6, score_threshold=0.4)
    else:
        print("No logged queries found. Run main.py first to generate logs.")

    print("\n" + "="*80)
    print("EVALUATION DEMO COMPLETE")
    print("="*80)
    print("\nYou can use these evaluation functions to:")
    print("  - Test different retrieval parameters")
    print("  - Compare confidence scores")
    print("  - Analyze retrieval quality")
    print("  - Optimize system performance")
    print()
    print("See evaluation.py for more functions and options.")
    print("="*80)


if __name__ == "__main__":
    main()
