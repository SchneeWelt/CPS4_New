import threading
import socket
from asyncio import SafeChildWatcher

import pigpio                                                   # GPIO Toolbox zur schnelleren Ansteuerung der IO-Pins
from time import sleep                                          # Zeitmethoden
from os import system

from stepper_motor_controller import StepperMotorController


# Schwelltemperatur in Grad Celsius, ab der die Lüfterklappe halb geöffnet werden soll.
SCHWELL_TEMPERATUR_LOW = 25

# Schwelltemperatur in Grad Celsius, ab der die Lüfterklappe ganz geöffnet werden soll.
SCHWELL_TEMPERATUR_HIGH = 30

# Konstanten, die den Zustand der Lüfterklappe beschreiben
STATE_FULLY_OPEN = 2
STATE_HALF_OPEN = 1
STATE_CLOSED = 0



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
        
        360   500
        1     
        65    90
        
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
        self.stepper_motor_controller = self._build_stepper_motor_controller()

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

            if not message_str:     # message_str == null?
                print("[fehler] Verbindung konnte nicht aufrecht gehalten werden...")

            # Message String vorab bearbeiten, um identifiezierung des Inhaltes zu erleichtern
            erhaltene_temperatur = float(message_str.lower())

            print(f"Temperatur erhalten: {erhaltene_temperatur} °C")


            """
            Die nachfolgende Schaltung funktioniert nur, wenn ein kontinuirlicher
            Übergang existiert. Ein Springen von Lüfterklappe geschlossen zu 
            Lüfterklappe Offen darf also nicht möglich sein. 
            Deshalb ist es nötig, dass mit einer möglichst hohen Frequenz
            die Temperatur erfasst wird, um starke Temperaturschwankungen
            rechtzeitig zu erkennen, bevor ein Bereich übersprungen wird. 
            """


            # Klappe soll geschlossen sein
            if erhaltene_temperatur <= SCHWELL_TEMPERATUR_LOW:

                # Temperatur ist kleiner als Low, aber Motor hat
                # Klappe noch nicht zu Low gedreht:

                if self.ventState != STATE_CLOSED:
                    # Motor auf Ruheposition drehen
                    self.stepper_motor_controller.rotiere_motor_counterclockwise(35)

                    # State aktualisieren
                    self.ventState = STATE_CLOSED

                print("[debug] Klappenzustand: " + str(self.ventState))

            # Klappe soll halb geöffnet sein
            elif erhaltene_temperatur <= SCHWELL_TEMPERATUR_HIGH:

                # Temperatur ist auf Mid, aber Motor hat Klappe noch
                # nicht zu Mid gedreht:

                if self.ventState != STATE_HALF_OPEN:

                    if self.ventState == STATE_CLOSED:  # Kommen wir von Closed?
                        self.stepper_motor_controller.rotiere_motor_clockwise(35)
                    elif self.ventState == STATE_FULLY_OPEN:    # Kommen wir von Open?
                        self.stepper_motor_controller.rotiere_motor_counterclockwise(90)

                    self.ventState = STATE_HALF_OPEN

                print("[debug] Klappenzustand: " + str(self.ventState))


            # Klappe soll ganz geöffnet sein
            elif erhaltene_temperatur > SCHWELL_TEMPERATUR_HIGH:

                # Temperatur ist auf High, aber Motor hat Klappe noch nicht
                # ganz geöffnet:

                if self.ventState != STATE_FULLY_OPEN:

                    self.stepper_motor_controller.rotiere_motor_clockwise(90)

                    self.ventState = STATE_FULLY_OPEN

                print("[debug] Klappenzustand: " + str(self.ventState))


    def _setup_daemon(self):
        system("sudo systemctl disable pigpiod")  # Disable des pigpio-daemon über die Kommandozeile
        sleep(0.5)  # Kleine Wartezeit
        system("sudo systemctl start pigpiod")  # Starte einen pigpio-daemon über die Kommandozeile
        sleep(1.0)


    def _build_stepper_motor_controller(self):

        steppins = [17, 18, 27, 22]  # GPIO Pins der Ansteuerschaltung. Diese Pins sind mit
                                     # dem Controller des Schrittmotors verbunden

        fullstepsequence = \
        (  # Schrittfolge der Ansteuerpins für den Vollschrittbetrieb in Vorwärtsrichtung
            (1, 0, 1, 0),
            (0, 1, 1, 0),
            (0, 1, 0, 1),
            (1, 0, 0, 1)
        )

        stepper_motor_controller = StepperMotorController(pigpio.pi(), steppins, fullstepsequence)
        stepper_motor_controller.set_stepper_delay(900)  # Achtung hier wird eine Frequenz übergeben! => schlechtes Design der Methode!

        return stepper_motor_controller


# Server wird bei ausführend des Scripts automatisch richtig konfiguriert und gestartet
server = SensorServer()