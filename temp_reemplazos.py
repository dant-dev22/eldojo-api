ruta = r'c:\Users\dante\Documents\trae_projects\eldojo-backend-api\manual_migration_20260821_seed_belts_all_orgs.sql'

with open(ruta, 'r', encoding='utf-8') as f:
    contenido = f.read()

contenido = contenido.replace("'ne-1', '1 Dan', '#F9A825'", "'ne-1', '1 Dan', '#212121'")
contenido = contenido.replace("'ne-2', '2 Dan', '#F9A825'", "'ne-2', '2 Dan', '#212121'")
contenido = contenido.replace("'ne-3', '3 Dan', '#F9A825'", "'ne-3', '3 Dan', '#212121'")
contenido = contenido.replace("'ne-4', '4 Dan', '#F9A825'", "'ne-4', '4 Dan', '#212121'")
contenido = contenido.replace("'rn-1', '5 Dan', '#FFFFFF'", "'rn-1', '5 Dan', '#212121'")
contenido = contenido.replace("'rn-2', '6 Dan', '#FFFFFF'", "'rn-2', '6 Dan', '#212121'")
contenido = contenido.replace("'rb-1', '7 Dan', '#FFFFFF'", "'rb-1', '7 Dan', '#212121'")
contenido = contenido.replace("'rb-2', '8 Dan', '#FFFFFF'", "'rb-2', '8 Dan', '#212121'")
contenido = contenido.replace("'ro-1', '9 Dan',  '#FFFFFF'", "'ro-1', '9 Dan',  '#212121'")
contenido = contenido.replace("'ro-2', '10 Dan', '#FFFFFF'", "'ro-2', '10 Dan', '#212121'")

with open(ruta, 'w', encoding='utf-8') as f:
    f.write(contenido)

print('Reemplazos completados.')
print()

with open(ruta, 'r', encoding='utf-8') as f:
    lineas = f.readlines()

en_belt_stripes = False
count_f9 = 0
count_ff = 0
for linea in lineas:
    if 'INSERT INTO belt_stripes' in linea:
        en_belt_stripes = True
    if en_belt_stripes:
        if '#F9A825' in linea:
            count_f9 += 1
        if '#FFFFFF' in linea:
            count_ff += 1
        if ';' in linea:
            en_belt_stripes = False

print('=== RESULTADO DE LA VERIFICACION ===')
print(f"Ocurrencias de '#F9A825' en lineas de INSERT INTO belt_stripes: {count_f9}")
print(f"Ocurrencias de '#FFFFFF' en lineas de INSERT INTO belt_stripes: {count_ff}")
