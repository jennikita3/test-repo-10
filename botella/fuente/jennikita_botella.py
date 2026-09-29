"""
Juego de la botella - Jennikita (botella y alfombra de SIXAMcc)

Rehecho desde cero en la versión 2. Todas las animaciones de los Sims son del juego:
  - Sentarse: las posturas del juego "de rodillas" (posture_Kneel) y "piernas
    cruzadas" (posture_CrossLegged), las mismas de "Sentarse en el suelo".
  - Girar: solo se anima la botella. Si el juego lo permite, el Sim gira sin
    levantarse; si no, se levanta, gira y luego vuelve a sentarse.
  - Beso: los dos se levantan (postura de pie del juego) y se besan con el
    beso del juego (Soc_Romance_T_Kiss_Embrace_Succeed_basic), dentro de una
    charla normal y sin las pruebas de romance del juego.
  - Animar: la animación del público del juego
    (reactionlets_Audience_CheerRandom), sentados si se puede.

Cómo se juega:
  "Jugar a la botella" abre un selector de Sims. Los elegidos se sientan en
  círculo alrededor de la botella, cada uno en su hueco. Cuando están todos
  sentados, cada uno gira la botella por turnos, en orden alrededor del
  círculo. La botella señala a un Sim sentado con el que se pueda besar: los
  dos se levantan y se besan, el resto anima y después todos vuelven a su
  sitio. Cuando todos han girado, se acaba el juego. Si un Sim se levanta por
  su cuenta (porque se lo mandas tú o porque tiene una necesidad urgente),
  sale del juego y el resto sigue.

Quién puede besarse: adolescentes con adolescentes, y jóvenes adultos,
adultos y ancianos entre sí. Nunca familiares.

v3 - El script sigue cada interacción que manda hasta que termina, en vez de
  buscarla en la cola del Sim (el juego no la enseña mientras el Sim camina o
  cambia de postura, y la v2 la daba por perdida y la volvía a mandar: por eso
  se levantaban sin parar, no se sentaban en círculo y la botella giraba tarde).
  Antes del beso los dos se levantan, porque el beso del juego no se puede
  hacer de rodillas ni sentado en el suelo.

El tuning usa clases del juego (así las interacciones siempre se cargan) y
este script les añade el comportamiento cuando el juego termina de cargar el
tuning (add_on_load_complete).

Compilar con Python 3.7 y meter el .pyc en un zip renombrado a
jennikita_botella.ts4script (máximo una carpeta de profundidad en Mods).
Lo que pasa en cada partida se apunta en jennikita_botella_log.txt, en la
carpeta Mods.

Comandos de trucos:
  jennikita.botella_estado      -> dice si el script está cargado y enganchado
  jennikita.botella_reiniciar   -> termina las partidas en curso por si algo
                                   se queda atascado.
"""
import math
import os
import random

import alarms
import services
import sims4.commands
import sims4.log
import sims4.math
import sims4.resources
from date_and_time import create_time_span
from interactions import ParticipantType
from interactions.aop import AffordanceObjectPair
from interactions.context import InteractionContext, QueueInsertStrategy
from interactions.interaction_finisher import FinishingType
from interactions.priority import Priority
from sims.sim_info_types import Age, Species
from sims4.localization import LocalizationHelperTuning
from sims4.utils import flexmethod
from ui.ui_dialog_notification import UiDialogNotification
from ui.ui_dialog_picker import SimPickerRow, UiSimPicker

VERSION = 3

# --- Registro -----------------------------------------------------------------

_logger_juego = sims4.log.Logger('JennikitaBotella', default_owner='Jennikita')

try:
    _RUTA_LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'jennikita_botella_log.txt')
    with open(_RUTA_LOG, 'w', encoding='utf-8') as _f:
        _f.write('Juego de la botella v{} - registro\n'.format(VERSION))
except Exception:
    _RUTA_LOG = None


def _log(texto, *args):
    try:
        if args:
            texto = texto.format(*args)
        try:
            hora = str(services.time_service().sim_now)
        except Exception:
            hora = '?'
        if _RUTA_LOG:
            with open(_RUTA_LOG, 'a', encoding='utf-8') as f:
                f.write('[{}] {}\n'.format(hora, texto))
    except Exception:
        pass


class _Registro:

    def error(self, texto, *args):
        _log('ERROR: ' + texto, *args)
        _logger_juego.error(texto, *args)

    def warn(self, texto, *args):
        _log('AVISO: ' + texto, *args)
        _logger_juego.warn(texto, *args)


logger = _Registro()

# --- Tuning -------------------------------------------------------------------

JUGAR = 'Jennikita:Botella_Jugar'
SENTARSE = ('Jennikita:Botella_Sentarse_Rodillas', 'Jennikita:Botella_Sentarse_Cruzado')
GIRAR = 'Jennikita:Botella_Girar_Accion'            # de pie
GIRAR_SENTADO = 'Jennikita:Botella_Girar_Sentado'   # dentro de "Sentarse"
LEVANTARSE = 'Jennikita:Botella_Levantarse'
BESO = 'Jennikita:Botella_Beso'
ANIMAR = 'Jennikita:Botella_Animar'                 # de pie
ANIMAR_SENTADO = 'Jennikita:Botella_Animar_Sentado' # dentro de "Sentarse"
SIM_CHAT = 13998  # sim_Chat, la charla normal del juego

# --- Ajustes ------------------------------------------------------------------

ANGULO_FINAL_BOTELLA = 160.0  # dónde queda el cuello de la botella al acabar la animación
RADIO_ASIENTO = 0.9
MARGEN_ASIENTO = 0.25
MAXIMO_JUGADORES = 8
PRIORIDAD_JUEGO = getattr(Priority, 'Critical', Priority.High)
ANIMAR_DE_PIE = True  # si no pueden animar sentados, se levantan a animar y vuelven a sentarse

# Esperas máximas, en minutos del juego (se revisa la partida una vez por
# minuto). Son solo por si algo se queda colgado: normalmente cada paso
# empieza en cuanto termina lo anterior.
ESPERA_SENTARSE = 120
ESPERA_VOLVER = 90
ESPERA_GIRO = 60
ESPERA_LEVANTARSE = 30
ESPERA_BESO = 90
INTENTOS_SENTARSE = 4  # veces que un Sim puede no llegar a sentarse antes de dejarle fuera
INTENTOS_CON_HUECO = 2  # a partir de aquí se sienta en cualquier sitio del círculo

TITULO = 'Juego de la botella'
TEXTO_SELECTOR = 'Elige quién se sienta a jugar alrededor de la botella.'
TEXTO_POCOS = 'Hacen falta al menos dos jugadores sentados alrededor de la botella.'
TEXTO_TURNO = 'Le toca girar la botella a {}.'
TEXTO_SIN_PAREJA = ('{} no tiene con quién besarse (hace falta alguien sentado de su misma franja '
                    'de edad y que no sea familia). Se salta su turno.')
TEXTO_SENALA = '¡La botella de {} señala a {}! Toca beso.'
TEXTO_PLANTON = '{} y {} no han llegado a besarse. ¡Otra vez será!'
TEXTO_FIN = '¡Fin del juego! Todos han girado la botella.'

# --- Estado -------------------------------------------------------------------

_JUEGOS = {}      # id de la botella -> _Juego
_SENTADOS = {}    # sim_id -> {id de su "Sentarse" en marcha: (id de la botella, interacción)}
_ASIENTOS = {}    # sim_id -> (id de la botella, posición, giro)
_POSTURA = {}     # sim_id -> nombre del "Sentarse" que usa (rodillas o cruzado)
_SIN_ASIENTO = set()  # sim_id que no llegan a su hueco: se sientan en cualquier sitio del círculo
_ENGANCHADAS = []


def _fnv64(texto):
    h = 0xCBF29CE484222325
    for c in texto.lower().encode('utf-8'):
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        h ^= c
    return h


def _id(nombre):
    return _fnv64(nombre) | 0x8000000000000000


_IDS_CHARLA = frozenset((SIM_CHAT,))


class _Juego:

    def __init__(self, botella):
        self.botella_id = botella.id
        self.jugadores = []     # sim_id en orden de turno
        self.fuera = set()      # sim_id que se han ido del juego
        self.turno = 0
        self.fase = 'sentando'
        self.espera = ESPERA_SENTARSE
        self.girador = None
        self.pareja = None
        self.reintentado = False
        self.giro_empezado = False
        self.beso_empezado = False
        self.charla = None
        self.mandadas = {}      # clave -> interacción que ha mandado el script
        self.fallos = {}        # sim_id -> veces seguidas que no ha llegado a sentarse
        self.alarma = None

    def botella(self):
        return services.object_manager().get(self.botella_id)


# --- Utilidades ---------------------------------------------------------------

def _afordancia(nombre):
    gestor = services.get_instance_manager(sims4.resources.Types.INTERACTION)
    return gestor.get(_id(nombre))


def _es(si, ids):
    return getattr(getattr(si, 'affordance', None), 'guid64', None) in ids


def _texto(texto):
    return lambda *_, **__: LocalizationHelperTuning.get_raw_text(texto)


def _aviso(texto):
    try:
        dialogo = UiDialogNotification.TunableFactory().default(None, title=_texto(TITULO), text=_texto(texto))
        dialogo.show_dialog()
    except Exception as e:
        logger.error('No se pudo mostrar el aviso: {}', e)


def _nombre(sim):
    return sim.sim_info.first_name


def _sim(sim_id):
    if sim_id is None:
        return None
    info = services.sim_info_manager().get(sim_id)
    if info is not None:
        return info.get_sim_instance()
    return None


def _contexto(sim, prioridad):
    return InteractionContext(sim, InteractionContext.SOURCE_SCRIPT, prioridad,
                              insert_strategy=QueueInsertStrategy.NEXT)


class _SinSeguimiento:
    """El juego aceptó la interacción pero no la devolvió: no se sabe cuándo
    termina, así que se da por pendiente hasta que se acabe la espera de la fase."""
    is_finishing = False
    sim = None

    def cancel(self, *args, **kwargs):
        self.is_finishing = True


def _creada(sim, nombre, resultado):
    interaccion = getattr(resultado, 'interaction', None)
    if interaccion is None:
        _log('{}: el juego no devuelve la interacción {} que se ha mandado', _nombre(sim), nombre)
        return _SinSeguimiento()
    return interaccion


def _pendiente(interaccion):
    """La interacción que mandamos aún no ha terminado (está en cola, caminando,
    cambiando de postura o en marcha)."""
    return interaccion is not None and not getattr(interaccion, 'is_finishing', True)


def _empezo(interaccion):
    return getattr(interaccion, '_jb_empezo', False)


def _empujar(sim, nombre, objetivo, prioridad=Priority.High):
    """Manda una interacción y devuelve la interacción creada (o None)."""
    afordancia = _afordancia(nombre)
    if afordancia is None:
        logger.error('No se encuentra la interacción {}', nombre)
        return None
    resultado = sim.push_super_affordance(afordancia, objetivo, _contexto(sim, prioridad))
    if not resultado:
        logger.warn('No se pudo mandar {} a {}: {}', nombre, _nombre(sim), resultado)
        return None
    _log('{} -> {}', _nombre(sim), nombre)
    return _creada(sim, nombre, resultado)


def _cancelar(interaccion, motivo):
    """Cancela una interacción que ha mandado el juego de la botella."""
    if interaccion is None or getattr(interaccion, 'is_finishing', False):
        return
    try:
        interaccion._jb_por_el_juego = True
        interaccion.cancel(FinishingType.USER_CANCEL, motivo)
        if interaccion.sim is not None:
            _log('{}: se cancela {} ({})', _nombre(interaccion.sim), interaccion.affordance.__name__, motivo)
    except Exception as e:
        logger.warn('No se pudo cancelar {}: {}', interaccion, e)


def _cancelar_charla(sim, motivo):
    if sim is None:
        return
    try:
        for si in tuple(sim.si_state or ()):
            if _es(si, _IDS_CHARLA):
                _cancelar(si, motivo)
    except Exception as e:
        logger.warn('No se pudo terminar la charla de {}: {}', _nombre(sim), e)


def _sentarse_en_marcha(sim, botella):
    for botella_id, si in _SENTADOS.get(sim.sim_id, {}).values():
        if botella_id == botella.id and not getattr(si, 'is_finishing', False):
            return si
    return None


def _esta_sentado(sim, botella):
    return _sentarse_en_marcha(sim, botella) is not None


def _levantar_del_juego(sim, botella, motivo):
    si = _sentarse_en_marcha(sim, botella)
    if si is not None:
        _cancelar(si, motivo)


def _franja(info):
    if info.species != Species.HUMAN:
        return None
    if info.age == Age.TEEN:
        return 'adolescente'
    if info.age in (Age.YOUNGADULT, Age.ADULT, Age.ELDER):
        return 'adulto'
    return None


def _familia(a, b):
    try:
        prueba = getattr(a, 'incest_prevention_test', None)
        if prueba is not None:
            return not prueba(b)
    except Exception as e:
        logger.warn('Fallo en incest_prevention_test: {}', e)
    return a.household_id == b.household_id


def _pueden_besarse(a, b):
    if a.sim_id == b.sim_id:
        return False
    franja = _franja(a)
    return franja is not None and franja == _franja(b) and not _familia(a, b)


def _angulo(botella, posicion):
    return math.atan2(posicion.x - botella.position.x, posicion.z - botella.position.z)


def _diferencia(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def _distancia(a, b):
    return math.hypot(a.x - b.x, a.z - b.z)


def _juego_de(botella):
    if botella is None:
        return None
    return _JUEGOS.get(botella.id)


def _presentes(juego):
    """Jugadores que siguen en el juego y están en el solar."""
    sims = []
    for sim_id in juego.jugadores:
        if sim_id in juego.fuera:
            continue
        sim = _sim(sim_id)
        if sim is not None:
            sims.append(sim)
    return sims


def _dejar_fuera(juego, sim_id, motivo):
    if sim_id in juego.fuera:
        return
    juego.fuera.add(sim_id)
    sim = _sim(sim_id)
    _log('{} sale del juego: {}', _nombre(sim) if sim is not None else sim_id, motivo)


# --- Mixers dentro de "Sentarse" ------------------------------------------------

def _mixer_cabe(sim, mixer, objetivo, si):
    """True si el mixer se puede hacer en la postura en la que está el Sim,
    False si no, y None si no se ha podido comprobar."""
    try:
        aop = AffordanceObjectPair(mixer, objetivo, si.affordance, si)
        restriccion = aop.constraint_intersection(sim=sim, posture_state=None)
        return bool(restriccion.intersect(sim.posture_state.posture_constraint_strict).valid)
    except Exception as e:
        _log('No se pudo comprobar si {} puede hacer {} sin levantarse: {}', _nombre(sim), mixer.__name__, e)
        return None


def _empujar_mixer(sim, nombre, objetivo, si):
    """Manda un mixer dentro de la interacción "Sentarse" que el Sim tiene en marcha."""
    mixer = _afordancia(nombre)
    if mixer is None:
        logger.error('No se encuentra la interacción {}', nombre)
        return None
    cabe = _mixer_cabe(sim, mixer, objetivo, si)
    if cabe is False:
        _log('{} no puede hacer {} sin levantarse', _nombre(sim), nombre)
        return None
    try:
        aop = AffordanceObjectPair(mixer, objetivo, si.affordance, si)
        resultado = aop.test_and_execute(_contexto(sim, PRIORIDAD_JUEGO))
    except Exception as e:
        logger.warn('Error al mandar {} a {}: {}', nombre, _nombre(sim), e)
        return None
    if not resultado:
        logger.warn('No se pudo mandar {} a {}: {}', nombre, _nombre(sim), resultado)
        return None
    _log('{} -> {} (sin levantarse)', _nombre(sim), nombre)
    return _creada(sim, nombre, resultado)


# --- Asientos -----------------------------------------------------------------

def _repartir_asientos(botella, sims):
    """Reparte los huecos en círculo alrededor de la botella, a la misma
    distancia entre sí. Los que ya están sentados se quedan con el hueco más
    cercano a donde están; a los demás les toca el hueco libre más cercano,
    para que caminen lo menos posible."""
    if not sims:
        return
    sentados = [s for s in sims if _esta_sentado(s, botella)]
    resto = [s for s in sims if s not in sentados]
    paso = 2 * math.pi / len(sims)
    base = _angulo(botella, (sentados or resto)[0].position)
    libres = [base + i * paso for i in range(len(sims))]
    centro = botella.position
    for sim in sentados + sorted(resto, key=lambda s: _angulo(botella, s.position)):
        angulo = _angulo(botella, sim.position)
        hueco = min(libres, key=lambda a: _diferencia(a, angulo))
        libres.remove(hueco)
        posicion = sims4.math.Vector3(centro.x + RADIO_ASIENTO * math.sin(hueco), centro.y,
                                      centro.z + RADIO_ASIENTO * math.cos(hueco))
        _ASIENTOS[sim.sim_id] = (botella.id, posicion, hueco + math.pi)


def _asiento(sim_id, botella):
    datos = _ASIENTOS.get(sim_id)
    if datos is not None and botella is not None and datos[0] == botella.id:
        return datos
    return None


def _hacer_constraint_sentarse(clase):
    """Añade a la restricción del tuning (anillo alrededor de la botella y
    postura del juego) un círculo en el hueco de cada Sim, para que cada uno
    camine a su sitio. Si un Sim no consigue llegar, se le quita (_SIN_ASIENTO)."""
    original = None
    for base in clase.__mro__:
        if '_constraint_gen' in base.__dict__:
            original = base.__dict__['_constraint_gen']
            break
    if original is None:
        return None
    from interactions.constraints import Circle

    def _constraint_gen(cls, inst, sim, target, participant_type=ParticipantType.Actor, **kwargs):
        if participant_type == ParticipantType.Actor and sim is not None and target is not None:
            try:
                datos = _asiento(sim.sim_id, target)
                if datos is not None and sim.sim_id not in _SIN_ASIENTO:
                    yield Circle(datos[1], MARGEN_ASIENTO, target.routing_surface)
            except Exception as e:
                logger.error('Error en la restricción del asiento: {}', e)
        yield from original.__get__(inst, cls)(sim, target, participant_type=participant_type, **kwargs)

    return flexmethod(_constraint_gen)


def _mandar_a_sentarse(sim, juego, botella):
    clave = ('sentarse', sim.sim_id)
    if _esta_sentado(sim, botella) or _pendiente(juego.mandadas.get(clave)):
        return
    nombre = _POSTURA.get(sim.sim_id)
    if nombre is None:
        nombre = _POSTURA[sim.sim_id] = random.choice(SENTARSE)
    interaccion = _empujar(sim, nombre, botella)
    juego.mandadas[clave] = interaccion
    if interaccion is None:
        _fallo_al_sentarse(juego, sim, 'no se le ha podido mandar')


def _fallo_al_sentarse(juego, sim, motivo):
    fallos = juego.fallos[sim.sim_id] = juego.fallos.get(sim.sim_id, 0) + 1
    _log('{} no ha podido sentarse ({}, intento {} de {})', _nombre(sim), motivo, fallos, INTENTOS_SENTARSE)
    if fallos >= INTENTOS_SENTARSE:
        _dejar_fuera(juego, sim.sim_id, 'no consigue sentarse')
    elif fallos >= INTENTOS_CON_HUECO and sim.sim_id not in _SIN_ASIENTO:
        _log('{} se sentará en cualquier sitio del círculo', _nombre(sim))
        _SIN_ASIENTO.add(sim.sim_id)


def _gestionar_asientos(juego, botella):
    """Manda a sentarse a quien no lo está y devuelve cuántos faltan por sentarse."""
    faltan = 0
    for sim in _presentes(juego):
        clave = ('sentarse', sim.sim_id)
        if _esta_sentado(sim, botella):
            continue
        if _pendiente(juego.mandadas.get(('animar', sim.sim_id))):
            faltan += 1  # está animando de pie; luego vuelve a sentarse
            continue
        anterior = juego.mandadas.get(clave)
        if _pendiente(anterior):
            faltan += 1  # va hacia su sitio
            continue
        if anterior is not None and not _empezo(anterior):
            juego.mandadas[clave] = None
            _fallo_al_sentarse(juego, sim, 'la interacción terminó sin llegar a sentarse')
            if sim.sim_id in juego.fuera:
                continue
        _mandar_a_sentarse(sim, juego, botella)
        if sim.sim_id not in juego.fuera:
            faltan += 1
    return faltan


# --- La partida ---------------------------------------------------------------

def _orientar_botella(botella, sim):
    """Gira la botella para que, al acabar la animación, el cuello apunte al Sim."""
    if botella.parent is not None:
        return
    dx = sim.position.x - botella.position.x
    dz = sim.position.z - botella.position.z
    giro = math.atan2(dx, dz) - math.radians(ANGULO_FINAL_BOTELLA)
    transformacion = sims4.math.Transform(botella.position, sims4.math.angle_to_yaw_quaternion(giro))
    botella.location = sims4.math.Location(transformacion, botella.routing_surface)


def _cambiar_fase(juego, fase, espera):
    _log('Fase: {} -> {}', juego.fase, fase)
    juego.fase = fase
    juego.espera = espera


def _siguiente_turno(juego, botella):
    while juego.turno < len(juego.jugadores):
        sim_id = juego.jugadores[juego.turno]
        juego.turno += 1
        sim = _sim(sim_id)
        if sim is None or sim_id in juego.fuera or not _esta_sentado(sim, botella):
            _log('Se salta el turno de un jugador que no está sentado')
            continue
        candidatos = [s for s in _presentes(juego)
                      if s is not sim and _esta_sentado(s, botella) and _pueden_besarse(sim.sim_info, s.sim_info)]
        if not candidatos:
            _log('{} no tiene con quién besarse: se salta su turno', _nombre(sim))
            _aviso(TEXTO_SIN_PAREJA.format(_nombre(sim)))
            continue
        pareja = random.choice(candidatos)
        juego.girador, juego.pareja = sim.sim_id, pareja.sim_id
        juego.reintentado = False
        juego.beso_empezado = False
        juego.charla = None
        _log('Turno de {} (le tocará a {})', _nombre(sim), _nombre(pareja))
        _aviso(TEXTO_TURNO.format(_nombre(sim)))
        _mandar_a_girar(juego, sim, botella, sentado=True)
        return
    _terminar_juego(juego, 'ronda completa')


def _mandar_a_girar(juego, sim, botella, sentado):
    juego.giro_empezado = False
    interaccion = None
    si = _sentarse_en_marcha(sim, botella)
    if sentado and si is not None:
        interaccion = _empujar_mixer(sim, GIRAR_SENTADO, botella, si)
    if interaccion is None:
        _levantar_del_juego(sim, botella, 'Le toca girar')
        interaccion = _empujar(sim, GIRAR, botella, PRIORIDAD_JUEGO)
    juego.mandadas['girar'] = interaccion
    _cambiar_fase(juego, 'girando', ESPERA_GIRO)


def _giro_terminado(juego, completo):
    botella = juego.botella()
    sim, pareja = _sim(juego.girador), _sim(juego.pareja)
    if botella is None:
        return
    if completo and sim is not None and pareja is not None and juego.pareja not in juego.fuera:
        _aviso(TEXTO_SENALA.format(_nombre(sim), _nombre(pareja)))
        _preparar_beso(juego, botella, sim, pareja)
        return
    if not juego.reintentado and sim is not None and juego.girador not in juego.fuera:
        _log('El giro de {} no se ha completado: se vuelve a mandar, esta vez de pie', _nombre(sim))
        juego.reintentado = True
        _mandar_a_girar(juego, sim, botella, sentado=False)
        return
    _log('El giro no se ha completado: se pasa al siguiente')
    _cambiar_fase(juego, 'volviendo', ESPERA_VOLVER)


def _preparar_beso(juego, botella, sim, pareja):
    """El beso del juego se hace de pie: primero se levantan los dos."""
    for clave, s in (('levantarse_a', sim), ('levantarse_b', pareja)):
        _levantar_del_juego(s, botella, 'Le ha tocado la botella')
        juego.mandadas[clave] = _empujar(s, LEVANTARSE, botella, PRIORIDAD_JUEGO)
    _cambiar_fase(juego, 'levantando', ESPERA_LEVANTARSE)


def _mandar_beso(juego):
    sim, pareja = _sim(juego.girador), _sim(juego.pareja)
    if sim is None or pareja is None:
        _abortar_beso(juego, 'uno de los dos ya no está')
        return
    _cambiar_fase(juego, 'besando', ESPERA_BESO)
    juego.mandadas['beso'] = _empujar_beso(sim, pareja)
    if juego.mandadas['beso'] is None:
        _abortar_beso(juego, 'no se pudo mandar el beso')


def _empujar_beso(sim, pareja):
    """Beso del juego: charla normal (sim_Chat) y dentro el beso de la botella,
    igual que cuando se elige una interacción social en el menú."""
    try:
        charla = services.get_instance_manager(sims4.resources.Types.INTERACTION).get(SIM_CHAT)
        beso = _afordancia(BESO)
        if charla is None or beso is None:
            logger.error('No se encuentra la charla ({}) o el beso ({})', charla, beso)
            return None
        si = None
        for s in tuple(sim.si_state or ()):
            grupo = getattr(s, 'social_group', None)
            if _es(s, _IDS_CHARLA) and grupo is not None and pareja in grupo:
                si = s
                break
        if si is None:
            resultado = sim.push_super_affordance(charla, pareja, _contexto(sim, PRIORIDAD_JUEGO), picked_object=pareja)
            if not resultado:
                logger.warn('No se pudo empezar la charla de {} con {}: {}', _nombre(sim), _nombre(pareja), resultado)
                return None
            si = resultado.interaction
        contexto = si.context.clone_for_continuation(si, insert_strategy=QueueInsertStrategy.NEXT,
                                                     source_interaction_id=si.id,
                                                     source_interaction_sim_id=sim.sim_id,
                                                     pick=si.context.pick,
                                                     preferred_objects=si.context.preferred_objects,
                                                     must_run_next=True)
        aop = AffordanceObjectPair(beso, pareja, charla, si, picked_object=pareja, push_super_on_prepare=True)
        resultado = aop.test_and_execute(contexto)
        if not resultado:
            logger.warn('No se pudo mandar el beso de {} a {}: {}', _nombre(sim), _nombre(pareja), resultado)
            return None
        _log('{} va a besar a {}: {}', _nombre(sim), _nombre(pareja), resultado)
        return _creada(sim, BESO, resultado)
    except Exception as e:
        logger.error('Error al mandar el beso: {}', e)
        return None


def _animar(juego, botella):
    for sim in _presentes(juego):
        if sim.sim_id in (juego.girador, juego.pareja):
            continue
        si = _sentarse_en_marcha(sim, botella)
        if si is None:
            continue
        interaccion = _empujar_mixer(sim, ANIMAR_SENTADO, botella, si)
        if interaccion is None and ANIMAR_DE_PIE:
            _cancelar(si, 'Animar a la pareja')
            interaccion = _empujar(sim, ANIMAR, botella, PRIORIDAD_JUEGO)
        juego.mandadas[('animar', sim.sim_id)] = interaccion


def _acabar_charla(juego):
    _cancelar(juego.charla, 'Fin del beso')
    for sim in (_sim(juego.girador), _sim(juego.pareja)):
        _cancelar_charla(sim, 'Fin del beso')


def _beso_terminado(juego, completo):
    _log('Termina el beso ({})', 'completo' if completo else 'cortado')
    _acabar_charla(juego)
    _cambiar_fase(juego, 'volviendo', ESPERA_VOLVER)


def _abortar_beso(juego, motivo):
    _log('No hay beso: {}', motivo)
    sim, pareja = _sim(juego.girador), _sim(juego.pareja)
    if sim is not None and pareja is not None:
        _aviso(TEXTO_PLANTON.format(_nombre(sim), _nombre(pareja)))
    _cancelar(juego.mandadas.get('beso'), 'No hay beso')
    _acabar_charla(juego)
    _cambiar_fase(juego, 'volviendo', ESPERA_VOLVER)


def _terminar_juego(juego, motivo, aviso=True):
    if _JUEGOS.get(juego.botella_id) is juego:
        del _JUEGOS[juego.botella_id]
    _log('Fin del juego: {}', motivo)
    try:
        if juego.alarma is not None:
            alarms.cancel_alarm(juego.alarma)
    except Exception:
        pass
    juego.alarma = None
    if aviso:
        _aviso(TEXTO_FIN if motivo == 'ronda completa' else TEXTO_POCOS)
    botella = juego.botella()
    for sim_id in juego.jugadores:
        sim = _sim(sim_id)
        if sim is not None and botella is not None:
            _levantar_del_juego(sim, botella, 'Fin del juego')
        _ASIENTOS.pop(sim_id, None)
        _POSTURA.pop(sim_id, None)
        _SIN_ASIENTO.discard(sim_id)


def _tick(juego):
    if _JUEGOS.get(juego.botella_id) is not juego:
        return
    botella = juego.botella()
    if botella is None:
        _terminar_juego(juego, 'la botella ya no está', aviso=False)
        return
    juego.espera -= 1
    if juego.fase in ('sentando', 'volviendo'):
        faltan = _gestionar_asientos(juego, botella)
        if faltan == 0 or juego.espera <= 0:
            sentados = [s for s in _presentes(juego) if _esta_sentado(s, botella)]
            if len(sentados) >= 2:
                _log('Siguiente turno con {} jugadores sentados (faltan {})', len(sentados), faltan)
                _cambiar_fase(juego, 'turno', 0)
            else:
                _terminar_juego(juego, 'no hay suficientes jugadores sentados')
    elif juego.fase == 'turno':
        _siguiente_turno(juego, botella)
    elif juego.fase == 'girando':
        giro = juego.mandadas.get('girar')
        if not _pendiente(giro):
            # Si hubiera acabado bien, _hacer_run_girar ya habría cambiado de fase.
            _log('El giro ha terminado sin completarse (empezó: {})', _empezo(giro))
            _giro_terminado(juego, False)
        elif juego.espera <= 0:
            _cancelar(giro, 'El giro tarda demasiado')
            _giro_terminado(juego, False)
    elif juego.fase == 'levantando':
        pendientes = [clave for clave in ('levantarse_a', 'levantarse_b') if _pendiente(juego.mandadas.get(clave))]
        if not pendientes or juego.espera <= 0:
            _mandar_beso(juego)
    elif juego.fase == 'besando':
        beso = juego.mandadas.get('beso')
        if not _pendiente(beso):
            _abortar_beso(juego, 'el beso ha terminado sin completarse (empezó: {}, {})'.format(
                juego.beso_empezado, getattr(beso, '_finisher', '')))
        elif juego.espera <= 0:
            _abortar_beso(juego, 'el beso tarda demasiado (empezó: {})'.format(juego.beso_empezado))


def _tick_seguro(juego):
    try:
        _tick(juego)
    except Exception as e:
        logger.error('Error en el turno ({}): {}', juego.fase, e)


def _empezar_juego(actor, botella, elegidos):
    juego = _JUEGOS.get(botella.id)
    nueva = juego is None
    if nueva:
        juego = _Juego(botella)
    for sim in elegidos:
        if sim.sim_id in juego.fuera:
            juego.fuera.discard(sim.sim_id)  # vuelve a jugar
            juego.fallos[sim.sim_id] = 0
    nuevos = [s for s in elegidos if s.sim_id not in juego.jugadores]
    if nueva and len(nuevos) < 2:
        _aviso(TEXTO_POCOS)
        return
    _repartir_asientos(botella, _presentes(juego) + nuevos)
    for sim in nuevos:
        juego.fallos[sim.sim_id] = 0
        _SIN_ASIENTO.discard(sim.sim_id)
        _POSTURA[sim.sim_id] = random.choice(SENTARSE)
    # Turnos en orden alrededor del círculo, empezando por quien abre el juego.
    base = _asiento(actor.sim_id, botella)
    base = base[2] if base is not None else 0.0
    nuevos.sort(key=lambda s: (_ASIENTOS[s.sim_id][2] - base) % (2 * math.pi))
    juego.jugadores.extend(s.sim_id for s in nuevos)
    if nueva:
        _JUEGOS[botella.id] = juego
        juego.alarma = alarms.add_alarm(botella, create_time_span(minutes=1),
                                        lambda _alarma: _tick_seguro(juego), repeating=True)
    _log('{} jugadores ({} nuevos): {}', len(juego.jugadores), len(nuevos), ', '.join(_nombre(s) for s in nuevos))
    for sim in _presentes(juego):
        if juego.fase in ('sentando', 'volviendo') or sim in nuevos:
            _mandar_a_sentarse(sim, juego, botella)


def _jugables(actor):
    """Sims que se pueden sentar a jugar: humanos de adolescente en adelante."""
    sims = [sim for sim in services.sim_info_manager().instanced_sims_gen() if _franja(sim.sim_info) is not None]
    sims.sort(key=lambda s: (s is not actor, s.sim_info.household_id != actor.sim_info.household_id, _nombre(s)))
    return sims


def _mostrar_selector(interaccion):
    actor, botella = interaccion.sim, interaccion.target
    sims = _jugables(actor)
    if not sims:
        return
    dialogo = UiSimPicker.TunableFactory().default(actor.sim_info,
                                                   title=_texto(TITULO),
                                                   text=_texto(TEXTO_SELECTOR),
                                                   min_selectable=1,
                                                   max_selectable=min(MAXIMO_JUGADORES, len(sims)),
                                                   should_show_names=True,
                                                   hide_row_description=False,
                                                   column_count=5)
    for sim in sims:
        dialogo.add_row(SimPickerRow(sim.sim_id, select_default=sim is actor, tag=sim.sim_info))

    def _elegidos(dialogo):
        if not dialogo.accepted:
            return
        try:
            elegidos = [info.get_sim_instance() for info in dialogo.get_result_tags()]
            _empezar_juego(actor, botella, [s for s in elegidos if s is not None])
        except Exception as e:
            logger.error('Error al sentar a los jugadores: {}', e)

    dialogo.add_listener(_elegidos)
    dialogo.show_dialog()


# --- Comportamiento de las interacciones ---------------------------------------

def _hacer_run_jugar(original):

    def _run_interaction_gen(self, timeline):
        try:
            _mostrar_selector(self)
        except Exception as e:
            logger.error('Error al abrir el selector de jugadores: {}', e)
        result = yield from original(self, timeline)
        return result

    return _run_interaction_gen


def _hacer_run_sentarse(original):

    def _run_interaction_gen(self, timeline):
        sim, botella = self.sim, self.target
        self._jb_empezo = True
        try:
            _SENTADOS.setdefault(sim.sim_id, {})[self.id] = (botella.id, self)
            juego = _juego_de(botella)
            if juego is not None:
                juego.fallos[sim.sim_id] = 0
            datos = _asiento(sim.sim_id, botella)
            if datos is not None:
                _log('{} se sienta a {:.2f} m de su hueco', _nombre(sim), _distancia(sim.position, datos[1]))
            else:
                _log('{} se sienta', _nombre(sim))
        except Exception as e:
            logger.error('Error al sentarse: {}', e)
        try:
            result = yield from original(self, timeline)
        finally:
            try:
                sentado = _SENTADOS.get(sim.sim_id, {})
                sentado.pop(self.id, None)
                if not sentado:
                    _SENTADOS.pop(sim.sim_id, None)
                juego = _juego_de(botella)
                if juego is not None and sim.sim_id in juego.jugadores \
                        and not getattr(self, '_jb_por_el_juego', False):
                    _dejar_fuera(juego, sim.sim_id, 'se ha levantado por su cuenta')
            except Exception as e:
                logger.error('Error al levantarse: {}', e)
        return result

    return _run_interaction_gen


def _hacer_run_girar(original):

    def _run_interaction_gen(self, timeline):
        self._jb_empezo = True
        juego = _juego_de(self.target)
        mio = juego is not None and juego.fase == 'girando' and juego.girador == self.sim.sim_id
        if mio:
            juego.giro_empezado = True
            juego.mandadas['girar'] = self
            try:
                pareja = _sim(juego.pareja)
                if pareja is not None:
                    _orientar_botella(self.target, pareja)
                _log('{} gira la botella', _nombre(self.sim))
            except Exception as e:
                logger.error('Error al preparar el giro: {}', e)
        result = yield from original(self, timeline)
        if mio and _JUEGOS.get(juego.botella_id) is juego and juego.fase == 'girando' \
                and juego.mandadas.get('girar') is self:
            try:
                _giro_terminado(juego, result is not False)
            except Exception as e:
                logger.error('Error al parar la botella: {}', e)
        return result

    return _run_interaction_gen


def _hacer_run_marcar(original):
    """Solo apunta que la interacción ha empezado (Levantarse)."""

    def _run_interaction_gen(self, timeline):
        self._jb_empezo = True
        result = yield from original(self, timeline)
        return result

    return _run_interaction_gen


def _juego_del_beso(interaccion):
    for juego in _JUEGOS.values():
        if juego.fase == 'besando' and juego.girador == interaccion.sim.sim_id \
                and juego.pareja == getattr(interaccion.target, 'sim_id', None):
            return juego
    return None


def _hacer_run_beso(original):

    def _run_interaction_gen(self, timeline):
        self._jb_empezo = True
        juego = _juego_del_beso(self)
        if juego is not None:
            juego.beso_empezado = True
            juego.mandadas['beso'] = self
            juego.charla = getattr(self, 'super_interaction', None)
            _log('Empieza el beso de {} y {}', _nombre(self.sim), _nombre(self.target))
            try:
                botella = juego.botella()
                if botella is not None:
                    _animar(juego, botella)
            except Exception as e:
                logger.error('Error al mandar a animar: {}', e)
        result = yield from original(self, timeline)
        if juego is not None and _JUEGOS.get(juego.botella_id) is juego and juego.fase == 'besando':
            try:
                _beso_terminado(juego, result is not False)
            except Exception as e:
                logger.error('Error al acabar el beso: {}', e)
        return result

    return _run_interaction_gen


def _hacer_run_animar(original):

    def _run_interaction_gen(self, timeline):
        self._jb_empezo = True
        result = yield from original(self, timeline)
        try:
            juego = _juego_de(self.target)
            if juego is not None and self.sim.sim_id in juego.jugadores and self.sim.sim_id not in juego.fuera:
                _mandar_a_sentarse(self.sim, juego, self.target)
        except Exception as e:
            logger.error('Error al acabar de animar: {}', e)
        return result

    return _run_interaction_gen


_COMPORTAMIENTOS = [
    ((JUGAR,), _hacer_run_jugar, None),
    (SENTARSE, _hacer_run_sentarse, _hacer_constraint_sentarse),
    ((GIRAR, GIRAR_SENTADO), _hacer_run_girar, None),
    ((LEVANTARSE, ANIMAR_SENTADO), _hacer_run_marcar, None),
    ((BESO,), _hacer_run_beso, None),
    ((ANIMAR,), _hacer_run_animar, None),
]
_TOTAL = sum(len(nombres) for nombres, _, _ in _COMPORTAMIENTOS)


def _enganchar(gestor=None):
    if gestor is None:
        gestor = services.get_instance_manager(sims4.resources.Types.INTERACTION)
    for nombres, hacer_run, hacer_constraint in _COMPORTAMIENTOS:
        for nombre in nombres:
            try:
                clase = gestor.get(_id(nombre))
                if clase is None:
                    logger.error('No se ha cargado el tuning {}', nombre)
                    continue
                if getattr(clase, '_jennikita_botella', False):
                    continue
                clase._run_interaction_gen = hacer_run(clase._run_interaction_gen)
                if hacer_constraint is not None:
                    nuevo = hacer_constraint(clase)
                    if nuevo is not None:
                        clase._constraint_gen = nuevo
                clase._jennikita_botella = True
                _ENGANCHADAS.append(nombre)
            except Exception as e:
                logger.error('No se pudo enganchar {}: {}', nombre, e)


try:
    services.get_instance_manager(sims4.resources.Types.INTERACTION).add_on_load_complete(_enganchar)
except Exception as _e:
    logger.error('No se pudo registrar el enganche: {}', _e)


# --- Trucos -------------------------------------------------------------------

@sims4.commands.Command('jennikita.botella_estado', command_type=sims4.commands.CommandType.Live)
def _cmd_estado(_connection=None):
    def salida(texto):
        sims4.commands.output(texto, _connection)

    salida('Juego de la botella v{}: interacciones enganchadas {} de {}.'.format(VERSION, len(_ENGANCHADAS), _TOTAL))
    for nombre in _ENGANCHADAS:
        salida('  - ' + nombre)
    for juego in _JUEGOS.values():
        salida('Partida: fase {}, turno {} de {}, {} sentados, {} fuera.'.format(
            juego.fase, juego.turno, len(juego.jugadores),
            sum(1 for datos in _SENTADOS.values() if any(b == juego.botella_id for b, _ in datos.values())),
            len(juego.fuera)))


@sims4.commands.Command('jennikita.botella_reiniciar', command_type=sims4.commands.CommandType.Live)
def _cmd_reiniciar(_connection=None):
    juegos = list(_JUEGOS.values())
    for juego in juegos:
        _terminar_juego(juego, 'reiniciado con el truco', aviso=False)
    _SENTADOS.clear()
    sims4.commands.output('Juego de la botella reiniciado: {} partidas terminadas.'.format(len(juegos)), _connection)
