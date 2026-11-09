"""Alarm table of the Ebara Hydrostation error word (gm-0011).

Generated 1:1 from the official app 2.0.10015 resources
(res/values/strings.xml and res/values-it/strings.xml). Do not edit the
table by hand.
"""
from __future__ import annotations

# mask: (code, severity, text_en, text_it, remedy_en, remedy_it)
ALARMS: dict[int, tuple[str, str, str, str, str, str]] = {
    0x0001: ('E01', 'alarm', 'Overtemperature alarm', 'Allarme di sovratemperatura', 'Verify that the conditions of installation and temperature environment are comply with the stated limits. The pump will restart automatically the moment the temperature drops belowthe stated limits', 'Verificare che le condizioni di installazione e di temperatura ambiente siano conformi ai limiti dichiarati. La pompa riparte in automatico nel momento in cui la temperatura scende entro i limiti indicati.'),
    0x0002: ('E02', 'alarm', 'Low Voltage alarm', 'Allarme di bassa tensione', 'Verify that the power supply mains supply complies to the stated minimum limits. The pump restarts automatically the moment the voltage mains voltage falls within the declared limits', 'Verificare che l’alimentazione di rete sia conforme ai limiti minimi dichiarati. La pompa riparte in automatico nel momento in cui la tensione di rete rientra entro i limiti dichiarati.'),
    0x0004: ('E02', 'alarm', 'Overvoltage alarm', 'Allarme di sovratensione', 'Verify that the power supply power supply complies with the stated maximum limits. The pump restarts automatically the moment the voltage mains voltage falls within the declared limits', 'Verificare che l’alimentazione di rete sia conforme ai limiti massimi dichiarati. La pompa riparte in automatico nel momento in cui la tensione di rete rientra entro i limiti dichiarati.'),
    0x0008: ('E03', 'alarm', 'Overcurrent alarm', 'Allarme di sovracorrente', 'Check for presence of any foreign bodies. Check the good condition of the bearings. The pump makes 3 attempts automatic resets, at the 4 intervention requires a manual reset.', 'Verificare presenza di eventuali corpi estranei. Verificare il buono stato dei cuscinetti. La pompa effettua 3 tentativi di reset automatici, al 4° intervento necessita un reset manuale.'),
    0x0020: ('E04', 'alarm', 'Short circuit between phases', 'Corto circuito tra le fasi', 'Contact the technical assistance', 'Contattare il servizio di assistenza tecnica.'),
    0x0100: ('E06', 'alarm', 'Pressure sensor fault', 'Sensore di pressione guasto', 'Check whether the sensor is obstructed by excessive scale. Provide cleaning or replacing of the sensor', 'Verificare se il sensore è ostruito da eccessiva formazione di calcare. Provvedere alla pulizia o alla sostituzione del sensore.'),
    0x0400: ('H01', 'warning', 'Dry march or working pressure ≤ a 0.5 BAR', 'Marcia a secco o pressione ≤ a 0,5 bar', 'Reduce the pressure value, reduce the demand for water, check the correct priming of the pump. The pump makes automatic reset attempts for a maximum time of about 3h.', 'Ridurre il valore di pressione, ridurre la richiesta di acqua, verificare il corretto adescamento della pompa. La pompa effettua dei tentativi di reset automatici per un tempo massimo di 3h circa.'),
    0x0800: ('H01+', 'warning', 'Lack of water on the suction side', 'Mancanza acqua lato aspirazione', 'Verify that the piping is in accordance with the directions in the manual, verify proper operation of the foot valve (if any), verify that there are no obstructions, verify proper priming. The pump makes automatic reset attempts for a maximum time of about 3h.', 'Verificare che le tubazioni siano conformi alle indicazioni presenti nel manuale, verificare corretto funzionamento della eventuale valvola di fondo, verificare che non vi siano ostruzioni, verificare il corretto adescamento. La pompa effettua dei tentativi di reset automatici per un tempo massimo di 3h circa.'),
    0x1000: ('H02', 'warning', 'Hourly restarts over the limit', 'Limite avviamenti orari oltre il limite', 'Check that the Δst value is not too low, in case increase value. Check for leaks in the system, in case repair the leaks. If necessary for the system configuration, check the presence and/or correct precharge of the water reserve expansion tank', 'Verificare che il valore Δst non sia troppo basso, nel caso aumentare valore. Verificare non vi siano perdite nell’impianto, nel caso riparare le perdite. Se necessario, per la configurazione dell’impianto, verificare la presenza e/o la corretta precarica del vaso di espansione di riserva idrica.'),
    0x2000: ('C01', 'warning', 'Communication error between devices', 'Errore di comunicazione tra apparecchi', 'Check the correct connection and integrity of the communication cable. Verify the correct setting for Twin communication.', 'Verificare il corretto collegamento ed integrità del cavo di comunicazione. Verificare il corretto settaggio per la comunicazione Twin.'),
}

# H01 text when the pump is configured in psi (status word bit 9).
H01_PSI = ('Dry march or working pressure ≤ a 8 psi', 'Marcia a secco o pressione ≤ a 8 psi')


def decode_codes(items: list[tuple[str, str]], psi: bool = False, lang: str = "en") -> list[dict[str, str]]:
    """Translate the alarms reported by the gateway as (code, english text)
    pairs, e.g. [("E01", "Overtemperature alarm"), ("H01+", "...")].

    The app uses the same code E02 for low and high voltage: the English text
    from the gateway ("Overvoltage ...") selects the right entry.
    """
    idx = 1 if lang.startswith("it") else 0
    result: list[dict[str, str]] = []
    for code, text_en in items:
        match = None
        for mask, entry in ALARMS.items():
            if entry[0] != code:
                continue
            if code == "E02" and (("over" in text_en.lower()) != (mask == 0x0004)):
                continue
            match = (mask, entry)
            break
        if match is None:
            # Code not in the app table: keep the gateway's own text rather
            # than hiding the alarm.
            result.append({"code": code, "severity": "unknown", "text": text_en.strip(), "remedy": ""})
            continue
        mask, (c, severity, t_en, t_it, r_en, r_it) = match
        text = H01_PSI[idx] if (mask == 0x0400 and psi) else (t_en, t_it)[idx]
        result.append({"code": c, "severity": severity, "text": text, "remedy": (r_en, r_it)[idx]})
    return result
