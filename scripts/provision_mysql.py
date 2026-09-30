"""Provision the dedicated local application account using temporary admin credentials."""
from pathlib import Path
import MySQLdb
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
c = dotenv_values(root / '.env')
admin_path = root / '.mysql-admin.env'
a = dotenv_values(admin_path)
user = c.get('DB_USER', c.get('MYSQL_USER', ''))
password = c.get('DB_PASSWORD', c.get('MYSQL_PASSWORD', ''))
if user != 'vanaraoncoscan' or not password:
    raise SystemExit('Expected the dedicated vanaraoncoscan username and a nonempty password in .env.')
if not a.get('MYSQL_ADMIN_USER') or not a.get('MYSQL_ADMIN_PASSWORD'):
    raise SystemExit('Enter the existing administrator username and password in .mysql-admin.env first.')
connection = None
try:
    connection = MySQLdb.connect(host=c.get('DB_HOST', c.get('MYSQL_HOST', '127.0.0.1')), port=int(c.get('DB_PORT', c.get('MYSQL_PORT', 3306))), user=a['MYSQL_ADMIN_USER'], passwd=a['MYSQL_ADMIN_PASSWORD'], connect_timeout=5)
    with connection.cursor() as cursor:
        cursor.execute('CREATE DATABASE IF NOT EXISTS `vanara_oncoscan` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        cursor.execute("CREATE USER IF NOT EXISTS %s@'localhost' IDENTIFIED BY %s", (user, password))
        cursor.execute("GRANT ALL PRIVILEGES ON `vanara_oncoscan`.* TO %s@'localhost'", (user,))
    connection.close()
    connection = None
    check = MySQLdb.connect(host=c.get('DB_HOST', c.get('MYSQL_HOST', '127.0.0.1')), port=int(c.get('DB_PORT', c.get('MYSQL_PORT', 3306))), user=user, passwd=password, db='vanara_oncoscan', connect_timeout=5)
    check.close()
    admin_path.write_text('MYSQL_ADMIN_USER=root\nMYSQL_ADMIN_PASSWORD=\n', encoding='utf-8')
    print('Dedicated account and database verified. Temporary administrator password cleared.')
except MySQLdb.Error as error:
    raise SystemExit(f'MySQL setup error {error.args[0]}. No passwords are displayed. Check administrator permissions or existing account configuration.') from None
finally:
    if connection:
        connection.close()
