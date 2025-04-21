#!/usr/bin/env python3
import os
import sys
from src.checktime.main import main, run_checker

if __name__ == "__main__":
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "web":
            os.environ['RUN_MODE'] = 'web_only'
            from src.checktime.web.app import app
            app.run(
                host='0.0.0.0',
                port=int(os.environ.get('PORT', 5000)),
                debug=os.environ.get('FLASK_ENV') == 'development'
            )
        elif mode == "checker":
            os.environ['RUN_MODE'] = 'checker_only'
            run_checker()
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python run.py [web|checker]")
            sys.exit(1)
    else:
        # Run both services
        main() 