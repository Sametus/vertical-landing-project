string = "12.5,13.45,0.0,1.0,0.002"
mesaj = string.split(",")
mesaj = [float(x) for x in mesaj]
print(mesaj)