import os
from dotenv import load_dotenv
from data.database import DatabaseManager

def main():
    # Load .env explicitly
    load_dotenv()
    print('Using server:', os.getenv('PAM_DB_SERVER'))
    mgr = DatabaseManager()
    try:
        ok = mgr.test_connection()
        if ok:
            print('SUCCESS: Database connection established.')
        else:
            print('FAIL: test_connection returned False')
    except Exception as e:
        print(f'ERROR: {e}')
        print('Server:', os.getenv('PAM_DB_SERVER'))
        print('Port:', os.getenv('PAM_DB_PORT'))
        print('Database:', os.getenv('PAM_DB_DATABASE'))
        user = os.getenv('PAM_DB_USERNAME')
        print('User set:' , 'yes' if user else 'no (Trusted_Connection)')

if __name__ == '__main__':
    main()
