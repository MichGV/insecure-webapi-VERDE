import json
import re
import random
import hashlib
import mysql.connector
import base64
import shutil
from datetime import datetime
from pathlib import Path
from bottle import route, run, template, post, request, static_file


def loadDatabaseSettings(pathjs):
    pathjs = Path(pathjs)
    sjson = False
    if pathjs.exists():
        with pathjs.open() as data:
            sjson = json.load(data)
    return sjson


def hashPassword(password, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 200000).hex()
    return f"{salt}${h}"


def checkPassword(password, stored):
    salt = stored.split('$')[0]
    return hmac.compare_digest(hashPassword(password, salt), stored)


def getToken():
    return secrets.token_hex(16)


@post('/Registro')
def Registro():
    dbcnf = loadDatabaseSettings('db.json')
    db = mysql.connector.connect(
        host='localhost', port=dbcnf['port'],
        database=dbcnf['dbname'],
        user=dbcnf['user'],
        password=dbcnf['password']
    )
    if not request.json:
        return {"R": -1}
    R = 'uname' in request.json and 'email' in request.json and 'password' in request.json
    if not R:
        return {"R": -1}
    if not all(str(request.json[k]).strip() for k in ('uname', 'email', 'password')):
        return {"R": -1}
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', str(request.json['email'])):
        return {"R": -1}
    R = False
    try:
        with db.cursor() as cursor:
            cursor.execute('insert into Usuario values(null,%s,%s,%s)', (request.json["uname"], request.json["email"], hashPassword(request.json["password"])))
            R = cursor.lastrowid
            db.commit()
        db.close()
    except Exception as e:
        print(e)
        return {"R": -2}
    return {"R": 0, "D": R}


@post('/Login')
def Login():
    dbcnf = loadDatabaseSettings('db.json')
    db = mysql.connector.connect(
        host='localhost', port=dbcnf['port'],
        database=dbcnf['dbname'],
        user=dbcnf['user'],
        password=dbcnf['password']
    )
    if not request.json:
        return {"R": -1}
    R = 'uname' in request.json and 'password' in request.json
    if not R:
        return {"R": -1}
    if not str(request.json['uname']).strip() or not str(request.json['password']).strip():
        return {"R": -1}
    R = False
    try:
        with db.cursor() as cursor:
            cursor.execute('select id, password from Usuario where uname=%s', (request.json["uname"],))
            R = cursor.fetchall()
    except Exception as e:
        print(e)
        db.close()
        return {"R": -2}

    if not R:
        db.close()
        return {"R": -3}

    T = getToken()

    try:
        with db.cursor() as cursor:
            cursor.execute('Delete from AccesoToken where id_Usuario = %s', (R[0][0],))
            cursor.execute('insert into AccesoToken values(%s,%s,now())', (R[0][0], T))
            db.commit()
            db.close()
            return {"R": 0, "D": T}
    except Exception as e:
        print(e)
        db.close()
        return {"R": -4}


@post('/Imagen')
def Imagen():
    tmp = Path('tmp')
    if not tmp.exists():
        tmp.mkdir()
    img = Path('img')
    if not img.exists():
        img.mkdir()

    if not request.json:
        return {"R": -1}
    R = 'name' in request.json and 'data' in request.json and 'ext' in request.json and 'token' in request.json
    if not R:
        return {"R": -1}
    ext = str(request.json['ext']).lower()
    if ext not in ('png', 'jpg', 'jpeg', 'gif'):
        return {"R": -1}

    dbcnf = loadDatabaseSettings('db.json')
    db = mysql.connector.connect(
        host='localhost', port=dbcnf['port'],
        database=dbcnf['dbname'],
        user=dbcnf['user'],
        password=dbcnf['password']
    )

    TKN = request.json['token']

    R = False
    try:
        with db.cursor() as cursor:
            cursor.execute('select id_Usuario from AccesoToken where token = %s', (TKN,))
            R = cursor.fetchall()
    except Exception as e:
        print(e)
        db.close()
        return {"R": -2}

    if not R:
        db.close()
        return {"R": -2}

    id_Usuario = R[0][0]
    with open(f'tmp/{id_Usuario}', "wb") as imagen:
        imagen.write(base64.b64decode(request.json['data'].encode()))

    try:
        with db.cursor() as cursor:
            cursor.execute('insert into Imagen values(null,%s,"img/",%s)', (request.json["name"], id_Usuario))
            cursor.execute('select max(id) as idImagen from Imagen where id_Usuario = '+str(id_Usuario))
            R = cursor.fetchall()
            idImagen = R[0][0]
            cursor.execute('update Imagen set ruta = "img/'+str(idImagen)+'.'+ext+'" where id = '+str(idImagen))
            db.commit()
            shutil.move('tmp/'+str(id_Usuario), 'img/'+str(idImagen)+'.'+ext)
            return {"R": 0, "D": idImagen}
    except Exception as e:
        print(e)
        db.close()
        return {"R": -3}


@post('/Descargar')
def Descargar():
    dbcnf = loadDatabaseSettings('db.json')
    db = mysql.connector.connect(
        host='localhost', port=dbcnf['port'],
        database=dbcnf['dbname'],
        user=dbcnf['user'],
        password=dbcnf['password']
    )

    if not request.json:
        return {"R": -1}
    R = 'token' in request.json and 'id' in request.json
    if not R:
        return {"R": -1}

    TKN = request.json['token']
    idImagen = request.json['id']

    R = False
    try:
        with db.cursor() as cursor:
            cursor.execute('select id_Usuario from AccesoToken where token = %s', (TKN,))
            R = cursor.fetchall()
    except Exception as e:
        print(e)
        db.close()
        return {"R": -2}

    if not R:
        db.close()
        return {"R": -2}
    id_Usuario = R[0][0]

    try:
        with db.cursor() as cursor:
            cursor.execute('Select name,ruta from Imagen where id = %s and id_Usuario = %s', (idImagen, id_Usuario))
            R = cursor.fetchall()
    except Exception as e:
        print(e)
        db.close()
        return {"R": -3}
    db.close()
    if not R:
        return {"R": -3}
    return static_file(R[0][1], Path(".").resolve())


if __name__ == '__main__':
    run(host='localhost', port=8080, debug=False)