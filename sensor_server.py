import threading
import socket
from asyncio import SafeChildWatcher

import pigpio                                                   # GPIO Toolbox zur schnelleren Ansteuerung der IO-Pins
from time import sleep                                          # Zeitmethoden
from os import system

from stepper_motor_controller import StepperMotor


# Schwelltemperatur in Grad Celsius, ab der die Lüfterklappe halb geöffnet werden soll.
SCHWELL_TEMPERATUR_LOW = 25

# Schwelltemperatur in Grad Celsius, ab der die Lüfterklappe ganz geöffnet werden soll.
SCHWELL_TEMPERATUR_HIGH = 30

# Konstanten, die den Zustand der Lüfterklappe beschreiben
STATE_FULLY_OPEN = 5
STATE_HALF_OPEN = 4
STATE_CLOSED = 3



class SensorServer:

    """
    Erzeugt ein Server Objekt.

    Dieser Server kann sich mit einem Client verbinden und von diesem
    Temperaturdaten in Grad Celsius erhalten. Der Server steuert mithilfe
    dieser Temperaturdaten dann eine Lüftungsklappe, die durch einen Schrittmotor
    angeschlossen am Server, gesteuert wird
    """

    def __init__(self):

        """
        Erzeugt einen Server, der auch direkt versucht sich mit einem Client
        zu verbinden.
        """

        """
        Berechnung der benötigten Anzahl an Schritten
        
        Annahme: Motor kann insgesamt 500 Schritte drehen. 
        
        Grad  Schritte
        360   500
        1     
        25    35
        
        360   500
        1     
        90    125
        
        """


        # Gibt den Zustand der Lüfterklappe an
        self.ventState = STATE_CLOSED

        # Diese Flag gibt an, ob der Server noch läuft
        self.running = True

        self.server = self._build_server(8000)

        # Genau eine Anfrage von einem Client entgegen nehmen.
        self.connected_client, self.addr = self.server.accept()

        # Motor für die Bedienung aktivieren
        self._setup_daemon()
        self.stepper_motor = self._build_stepper_motor()

        self._oeffne_verbindung()


    def _schließe_server(self):

        """
        Der Aufruf von dieser Methode beendet den Server.
        senden.

        :return:
        """

        print()
        print("[debug] Schließe Server")

        self.running = False


        # Die letzte Eingabe ist erforderlich, da input() den sending channel blockiert. Dieses Problem könnte laut
        # Copilot durch die Verwendung von einer Queue Datenstruktur, welche durch einen separaten Thread mit dem
        # Inhalt des Aufrufes Input gefüllt wird, gelöst werden. Da in diesem Studiengang das Konzept von Queue aber
        # noch nirgends gelehrt wurde, haben wir jetzt mal auf die Verwendung verzichtet und behelfen uns mit einer
        # - durchaus sinnvollen - zusätlichen Eingabe. Schließlich könnte hier dem Server noch mitgeteilt werden,
        #  wie er bspw mit dem Server Log umgehen soll: soll er es speichern, löschem etc.
        print("[server] Warte auf letzte Eingabe...")

        # self.receiving_channel.join() # Den nicht join, da diese Methode von diesem Thread selbst aufgerufen wird
        self.sending_channel.join()

        self.server.close()

        print("[debug] Server wurde erfolgreich geschlossen")


    def _oeffne_verbindung(self):

        """
        Diese Methode staret zwei Threads. Der eine sorgt dafür, dass der
        Server Daten von einem Client empfangen kann, der ander dafür, dass
        der Server Daten senden kann.

        :return:
        """

        self.receiving_channel = threading.Thread(target=self.receive)
        self.receiving_channel.start()

        self.sending_channel = threading.Thread(target=self.send)
        self.sending_channel.start()


    def _build_server(self, server_port):

        """
        Initialisiert das Server Objekt. Der Server wird dabei
        direkt richtig konfiguriert.

        :param server_port: Der Port auf dem der Server läuft.
        :return: Das erzeugte Server Objekt.
        """

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Server einrichten
        server_address = '0.0.0.0'  # 127.0.0.1 invalid, wir brauchen 0.0.0.0 was gleichbedeutent zu "" ist
        server.bind((server_address, server_port))

        server.listen(10)  # Dieser Server nimt nur genau 10 Clients an.

        return server


    def send(self):

        """
        Diese Methode wird vom Server in einem separaten Thread gestartet.
        Sie ermöglicht dem Server Nachrichten an einen verbunden Client zu senden.

        :return:
        """

        while self.running:
            message_string = input("> ")

            if (self.running): # Nicht redundant, da input() blockiert und in dieser Zeit running bereits false werden kann
                self.connected_client.send(message_string.encode('utf-8'))


    def receive(self):

        """
        Diese Methode wird vom Server in einem separaten Thread gestartet.
        Sie ermöglicht es dem Server Nachrichten von einem Client zu empfangen.
        :return:
        """

        # Eingabeloop für Steuerung des Motors starten
        while self.running:
            message_str = self.connected_client.recv(1024).decode('utf-8')

            if not message_str:
                print("[fehler] Verbindung konnte nicht aufrecht gehalten werden...")

            # Message String vorab bearbeiten, um identifiezierung des Inhaltes zu erleichtern
            erhaltene_temperatur = int(message_str.lower())

            # Klappe ist geschlossen
            if erhaltene_temperatur <= SCHWELL_TEMPERATUR_LOW:

                # Temperatur ist kleiner als Low, aber Motor hat
                # Klappe noch nicht zu Low gedreht:

                if self.ventState != STATE_CLOSED:
                    # Motor auf Ruheposition drehen
                    self._rotiere_motor_um_schritte_anti_clockwise(35)

                    # State aktualisieren
                    self.ventState = STATE_CLOSED

                print("[debug] Zustand: " + str(STATE_CLOSED))

            elif erhaltene_temperatur <= SCHWELL_TEMPERATUR_HIGH:

                # Temperatur ist auf Mid, aber Motor hat Klappe noch
                # nicht zu Mid gedreht:

                if self.ventState != STATE_HALF_OPEN:

                    if self.ventState == STATE_CLOSED:  # Kommen wir von Closed?
                        self._rotiere_motor_um_schritte_clockwise(35)
                    elif self.ventState == STATE_FULLY_OPEN:    # Kommen wir von Open?
                        self._rotiere_motor_um_schritte_anti_clockwise(125)

                    self.ventState = STATE_HALF_OPEN

                print("[debug] Zustand: " + str(STATE_HALF_OPEN))


            elif erhaltene_temperatur > SCHWELL_TEMPERATUR_HIGH:

                # Temperatur ist auf High, aber Motor hat Klappe noch nicht
                # ganz geöffnet:

                if self.ventState != STATE_FULLY_OPEN:

                    self._rotiere_motor_um_schritte_clockwise(125)

                    self.ventState = STATE_FULLY_OPEN

                print("[debug] Zustand: " + str(STATE_FULLY_OPEN))


    def _rotiere_motor_um_schritte_clockwise(self, anzahl_schritte):

        """
        Dreht den Motor um die übergebene Anzahl an Schritten

        :param anzahlSchritte:
        :return:
        """

        for i in range(25):
            self.stepper_motor.do_clockwise_step()



    def _rotiere_motor_um_schritte_anti_clockwise(self, anzahl_schritte):

        """

        :param anzahl_schritte:
        :return:
        """

        for i in range(25):
            self.stepper_motor.do_anticlockwise_step()



    def _setup_daemon(self):
        system("sudo systemctl disable pigpiod")  # Disable des pigpio-daemon über die Kommandozeile
        sleep(0.5)  # Kleine Wartezeit
        system("sudo systemctl start pigpiod")  # Starte einen pigpio-daemon über die Kommandozeile
        sleep(1.0)


    def _build_stepper_motor(self):

        steppins = [17, 18, 27, 22]  # GPIO Pins der Ansteuerschaltung. Diese Pins sind mit
                                     # dem Controller des Schrittmotors verbunden

        fullstepsequence = \
        (  # Schrittfolge der Ansteuerpins für den Vollschrittbetrieb in Vorwärtsrichtung
            (1, 0, 1, 0),
            (0, 1, 1, 0),
            (0, 1, 0, 1),
            (1, 0, 0, 1)
        )

        stepper_motor = StepperMotor(pigpio.pi(), steppins, fullstepsequence)
        stepper_motor.set_stepper_delay(900)  # Achtung hier wird eine Frequenz übergeben! => schlechtes Design der Methode!

        return stepper_motor


# Server wird bei ausführend des Scripts automatisch richtig konfiguriert und gestartet
server = SensorServer()