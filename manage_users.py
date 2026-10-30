"""Primera cuenta: python manage_users.py create-admin"""
import argparse, getpass, sys
from src.database.store import init_db
from src.core.auth import init_auth,create_user,user_count

def main():
    p=argparse.ArgumentParser(description='Creación inicial de administrador de Nariño 360')
    p.add_argument('command',choices=['create-admin'])
    a=p.parse_args();init_db();init_auth()
    if user_count():
        print('Ya existen usuarios. Usa Administración dentro de la aplicación para crear otros.');return 1
    username=input('Usuario administrador: ').strip()
    nombre=input('Nombre completo: ').strip()
    password=getpass.getpass('Contraseña (mínimo 12 caracteres): ')
    confirmation=getpass.getpass('Repetir contraseña: ')
    if password!=confirmation:print('Las contraseñas no coinciden.');return 1
    try:create_user(username,nombre,'Administrador',password)
    except Exception as exc:print(f'Error: {exc}');return 1
    print('Administrador creado. Inicia sesión en Streamlit.');return 0
if __name__=='__main__':sys.exit(main())
