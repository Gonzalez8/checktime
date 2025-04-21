import os
from checktime.web import create_app

app = create_app()

if __name__ == '__main__':
    # Get port from environment variable or use default 5000
    port = int(os.environ.get('PORT', 5000))
    
    app.run(
        host='0.0.0.0',  # Make the server accessible externally
        port=port,
        debug=os.environ.get('FLASK_ENV') == 'development'
    ) 