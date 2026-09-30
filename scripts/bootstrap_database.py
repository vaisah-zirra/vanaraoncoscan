"""Create only the configured application schema; never drop existing data."""
import os
from pathlib import Path
import MySQLdb
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
name = os.environ.get('MYSQL_DATABASE', 'vanara_oncoscan')
if name != 'vanara_oncoscan':
    raise SystemExit('This bootstrap is restricted to the vanara_oncoscan schema.')
if not os.environ.get('MYSQL_USER'):
    raise SystemExit('Set MYSQL_USER and MYSQL_PASSWORD privately in .env first.')
try:
    connection = MySQLdb.connect(host=os.environ.get('MYSQL_HOST', '127.0.0.1'), port=int(os.environ.get('MYSQL_PORT', '3306')), user=os.environ['MYSQL_USER'], passwd=os.environ.get('MYSQL_PASSWORD', ''))
    with connection.cursor() as cursor:
        cursor.execute('CREATE DATABASE IF NOT EXISTS `vanara_oncoscan` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
    connection.close()
except MySQLdb.Error as error:
    raise SystemExit(f'MySQL setup failed (error {error.args[0]}). Check local credentials and schema-creation permission.') from None
print('MySQL schema vanara_oncoscan is available.')
