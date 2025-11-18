import pigpio                                                   # GPIO Toolbox zur schnelleren Ansteuerung der IO-Pins
from time import sleep                                          # Zeitmethoden
from collections import deque                                   # Die einzelnen Schaltbefehle werden als Queue verwaltet
from os import system                                           # Zugriff auf die Kommandozeile des Raspberry PI

class StepperMotor:
    def __init__(self, pi, stepp_pins, sequence):

        """
        :param pi:
        :param stepp_pins: Die Pins, welche jeweils die Spulen ansteuern. Bei einem 4-Phasigen Stepper Motor
        wären das entsprechend 4 Pins. Dieses Objekt soll als Liste übergeben werden, welche 4 Integer
        enthält.
        :param sequence: Ein 4-Tupel bestehend aus 4-Tupeln. Jedes Tupel gibt die Schaltweise für die vier
        unterschiedlichen Spulen für je einen Schritt vor. Die Reinfolge beeinflusst maßgeblich, ob der Schrittmotor
        korrekt läuft und ob er überhaupt läuft. Durch Ändern der Reinfolge der 4-Tupel ist auch eine Änderung der
        Drehrichtung des angesteuerten Motors möglich.
        """

        # Sicherheitsabfragen
        self._check_pigpio_existence()

        # Zuweisungen im Objektspeicher
        self.pi = pi
        self.__delay_after_step = None                              # Periodendauer der Schrittfolge (geschützt als private)
        self.stepp_pins = stepp_pins

        self.deque = self._build_sequence_qeueue(sequence)

        # Funktionalität bei Objekterzeugung
        self._set_all_available_pins_as_output(stepp_pins)


    def _build_sequence_qeueue(self, sequence):

        """
        Baut ein Qeueu Objekt, welches später im Objekt für die richtige
        Ansteuerung der Spulen im Schritt Motor verwendet wird.
        :param sequence:
        :return:
        """

        return deque(sequence)


    def _check_pigpio_existence(self):

        if not isinstance(self.pi, pigpio.pi):
            raise TypeError("Der Daemon pigpio.pi ist nicht instanziert!")


    def _set_all_available_pins_as_output(self, pins):
        for pin in pins:
            self.pi.set_mode(pin, pigpio.OUTPUT)


    def set_stepper_delay(self, step_freq):                      # Methode zum Setzen der Schrittfrequenz

        """
        Gibt an, wie viel Zeit vergehen soll, bis der nächste Schritt
        durch den Schrittmotor durchgeführt werden soll

        :param step_freq: Die Frequenz in Hz mit der sich der Schrittmotor
        drehen soll.
        :return:
        """

        if step_freq > 0 and step_freq < 1500:                  # Nur gültige Frequenzen werden zugelassen.
            self.__delay_after_step = 1 / step_freq


    def do_counterclockwise_step(self):

        """
        Bewegt den Schrittmotor einen Schritt nach vorne. Die
        Drehrichtung läuft entgegen dem Urhzeigersinn.

        :return:
        """

        self.deque.rotate(-1)                                   # Gehe in der Queue um einen Schritt zurück
        self.do_step_and_delay(self.deque[0])                   # Übergebe die aktuelle Bitcodierung des Schritts


    def do_clockwise_step(self):

        """
        Bewegt den Schrittmotor einen Schritt nach vorne. Die
        Drehrichtung läuft mit dem  Urhzeigersinn.

        :return:
        """

        self.deque.rotate(1)                                    # Gehe in der Queue um einen Schritt vor
        self.do_step_and_delay(self.deque[0])                   # Übergebe die aktuelle Bitcodierung des Schritts


    def do_step_and_delay(self, step):

        """
        Diese Methode lässt den Schrittmotor um einen Schritt weiter
        drehen. Über die Verwendung des Parameters wäre auch das
        Springen zu einem anderen Zustand möglich. Dies ist aber nicht
        sinnvoll!


        :param step:
        Das Tupel, welches vorgeben soll, welche Pins angesteuert
        werden müssen.

        So wie ich das sehe ist der Parameter gar nicht notwenig,
        da eh immer ein konstaner Wert, abhängig vom Zustand der queue, übergeben
        wird
        :return:
        """

        tupel_item_index = 0
        for pin in self.stepp_pins:                                    # Setze die Ausangspins gemäß der Bitcodierung
            self.pi.write(pin, step[tupel_item_index])
            tupel_item_index += 1

        sleep(self.__delay_after_step)                          # Wartezeit bis zum nächsten Schritt


    def disable_stepper_motor(self):

        """
        Diese Methode kann zum deaktivieren des Stepper Motors verwendet werden.
        Nach Ausführung von diesem Befehl ist ein Ansteuern des Motors über
        dieses Objekt nicht mehr möglich.

        :return:
        """

        for pin in self.stepp_pins:                           # Alle gültigen Pins werden auf off geschaltet
            self.pi.write(pin, 0)