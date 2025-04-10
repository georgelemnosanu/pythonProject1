from sense_hat import SenseHat
import time

sense = SenseHat()
while True:
    try:
        humidity = sense.get_humidity()
        print("Humidity:", humidity)
    except Exception as e:
        print("Error reading humidity:", e)
    time.sleep(2)