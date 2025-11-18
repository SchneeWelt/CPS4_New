import socket
import threading
from time import sleep
import math
import Adafruit_ADS1x15

adc = Adafruit_ADS1x15.ADS1115()
adc_channel_0 = 0
GAIN = 1  # für ±4.096V, passend für 3.3V Messbereich


class SensorClient:

    """
    Erzeugt ein Client Objekt, welches mit einem Server kommunizieren kann.

    Dabei misst dieser Client die Temperatur über einen, an ihn angeschlossenen
    Sensor. Er überträg die Gemessene Temperatur an den Server. Der Server
    verarbeitet diesen Wert dann bei sich. ...
    """

    def __init__(self, simulierte_verbindung = False):

        self.simulierte_verbindung = simulierte_verbindung;
        server_port = 8000
        server_address = '192.168.178.134'

        self.running = True

        # Verbindung zum Server alias: client Objekt

        if not self.simulierte_verbindung:                #Wenn es keine simulierte Verbindung ist, dann funktioniert alles wie gewohnt
            self.server_connection = self._connect_to_server(server_port, server_address)

        self._oeffne_verbindung()


    def _oeffne_verbindung(self):

        self.receiving_connection = threading.Thread(target = self.receive, args = (self.server_connection,))
        self.receiving_connection.start()

        self.sending_connection = threading.Thread(target = self.send, args = (self.server_connection,))  # Das Komma nach client ist erforderlich, da sonst kein 2-Tuple gebildet wird, sondern nur ein Objekt in Klammern übergeben wird
        self.sending_connection.start()


    def _schließe_verbindung(self):

        print("[debug] Beende Verbindung mit Server")

        self.running = False

        self.receiving_connection.join()
        # self.sending_connection.join()   # Den nicht joinen, da diese methdoe von diesem thread selbst aufgerufen wird

        self.server_connection.close()


    def _connect_to_server(self, server_port, server_address):

        """
        Sorgt dafür, dass dieser Client versucht sich mit einem Server zu
        verbinden. Hat diese erfolgreich funktioniert, so wird das client
        Objekt zurückgegeben. (Andernfalls aber auch...)

        :param server_port:
        :param server_address:
        :return:
        """

        sever_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)        # server_connection aka client
        sever_connection.connect((server_address, server_port))

        return sever_connection


    def receive(self, client_socket):

        """
        Empfängt Daten von einem Server

        :param client_socket:
        :return:
        """

        while self.running:
            message_string = client_socket.recv(1024).decode('utf-8')

            if not message_string:
                break # Verwendung von break => Senden von "" schließt Verbindung ebenfalls

            print("\nNachricht vom Server: ", message_string)
            if (self.running):  # Nicht redundant, da Server hier die Flag auf False setzt, sobald Verbidung gekappt
                print("> ", end="")




    def send(self, client_socket):

        """
        Sendet gemessene Temperaturwerte an einen, mit dem Client verbundenen
        Server

        :return:
        """

        while self.running:
            if self.simulierte_verbindung:          #If Abfrage ob es (zu testzwecken) simulierte oder echte werte sein sollen
                spannung = 2.5;                     #Manuell gesetzter Spannungswert
                temperature = self._convert_measured_voltage_to_temperature(spannung)
            else:
                #Hier würde die tatsächliche Messung erfolgen
                adc_value = adc.read_adc(adc_channel_0, gain=GAIN)
                spannung = (adc_value / 32768.0) * 4.096
                temperature = str(self._convert_measured_voltage_to_temperature(spannung))


            # Temperaturdatum in Temperaturwert umrechnen

            # Temperaturwert an Server senden
            # temperatur_str = f"{temperature:.1f}"                        #f-String wird auf eine Nachkommastelle abgerundet
            # print(f"Send: {temperatur_str} °C")

            self.server_connection.send(temperature.encode('utf-8'))

            sleep(1000)                         # Nur jede Sekunde Messen.


    def _convert_measured_voltage_to_temperature(self, measured_voltage):

        """
        Ausgabe in Grad Celsius, eingabe zwischen 0 und 5 Volt.
        :param measured_voltage:
        :return:
        """

        temperature = math.log((10_000 / measured_voltage) * (3300 - measured_voltage))
        temperature = 1 / (
                    0.001129148 + (0.000234125 + (0.000_000_0876741 * temperature * temperature)) * temperature)
        return temperature - 237.15


# Bei Ausführung des Scripts startet der Client automatisch.
client = SensorClient()





