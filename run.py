"""
AQI Forecaster — Quick Start Runner
=====================================
Runs:  python run.py
Optionally seeds DB and trains models before starting Flask.

Usage:
    python run.py              # just start the server
    python run.py --seed       # seed DB then start
    python run.py --train      # train models then start
    python run.py --all        # seed + train + start
"""
import argparse
import subprocess
import sys
import os
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))


def run(cmd, **kwargs):
    print(f"\n▶  {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"❌ Command failed (exit {result.returncode})")
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="AQI Forecaster Launcher")
    parser.add_argument("--seed",  action="store_true", help="Seed the database first")
    parser.add_argument("--train", action="store_true", help="Train ML models first")
    parser.add_argument("--all",   action="store_true", help="Seed + train + start")
    parser.add_argument("--days",  type=int, default=30, help="Days of data to seed (default: 30)")
    args = parser.parse_args()

    python = sys.executable

    print("""
╔══════════════════════════════════════════╗
║   🌫️  AQI Forecaster — Quick Start      ║
╚══════════════════════════════════════════╝
    """)

    if args.all or args.seed:
        print(f"📦 Seeding database with {args.days} days of data...")
        run([python, str(BASE / "backend" / "utils" / "seed_db.py"), "--days", str(args.days)])

    if args.all or args.train:
        print("🧠 Training ML models for all 20 cities...")
        run([python, str(BASE / "backend" / "ml" / "forecaster.py")])

    print("🚀 Starting Flask server on http://localhost:5005 ...")
    os.chdir(BASE)
    run([python, str(BASE / "backend" / "app.py")])


if __name__ == "__main__":
    main()
