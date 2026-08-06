import argparse
import random
import json
import sys

def main():
    parser = argparse.ArgumentParser(description="Roll some dice.")
    parser.add_argument("--sides", type=int, default=6, help="Number of sides on the die")
    parser.add_argument("--count", type=int, default=1, help="Number of dice to roll")
    args = parser.parse_args()

    try:
        if args.sides < 1:
            raise ValueError("Sides must be at least 1")
        if args.count < 1:
            raise ValueError("Count must be at least 1")

        results = [random.randint(1, args.sides) for _ in range(args.count)]
        total = sum(results)
        
        output = {
            "status": "success",
            "results": results,
            "total": total,
            "details": f"Rolled {args.count}d{args.sides}"
        }
        print(json.dumps(output))
        
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
