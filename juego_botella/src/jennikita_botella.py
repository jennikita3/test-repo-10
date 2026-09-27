"""
Juego de la botella - Jennikita (botella y alfombra de SIXAMcc, animaciones de Love4Sims)

Interacciones de la botella (el tuning está en el .package):
  - Jugar a la botella: abre un selector de Sims. Los elegidos van a sentarse
    en círculo alrededor de la botella, cada uno de rodillas o con las piernas
    cruzadas al azar. Solo los Sims sentados pueden salir en la botella.
  - Por turnos, cada Sim sentado gira la botella: se elige al azar un Sim
    sentado con el que pueda besarse, se orienta la botella para que acabe
    apuntándole, se reproduce el giro y después los dos se colocan uno frente
    al otro y se besan. El resto de Sims sentados animan y luego vuelven a
    sentarse.

Quién puede besarse: adolescentes con adolescentes, y jóvenes adultos,
adultos y ancianos entre sí. Nunca niños ni familiares.

v8 - Arreglo de los Sims invisibles (junto con el .package nuevo):
  - Sentarse ya no usa "mixers": el .package usa ahora contenido en bucle
    (looping_content), como los mods que funcionan, y las animaciones salen
    del ASM al terminar. El giro, el beso y animar también terminan en "exit".
  - Al colocar a un Sim en su asiento se usa su propia altura y superficie,
    no la de la botella (si la botella está encima de la alfombra el Sim
    quedaba colocado a otra altura).
  - Los tiempos de espera usan el reloj del juego (antes usaban el reloj real
    y, con el juego en pausa o a velocidad 3, los turnos se saltaban o se
    eternizaban).
  - Se quita la lectura del árbol genealógico que fallaba en cada comprobación
    ('GenealogyTracker' object has no attribute 'get_family_sim_ids'). Se usa
    la prueba de incesto del juego.

v7 - Juego automático: "Jugar a la botella" sienta a los elegidos y, cuando
  están todos sentados, cada uno gira la botella por turnos (en orden alrededor
  del círculo) sin tener que dar ninguna otra orden. Al acabar la ronda se
  levantan. "Girar la botella" ya no sale en el menú.

Compilar con Python 3.7 y meter el .pyc en un zip renombrado a
jennikita_botella.ts4script (máximo una carpeta de profundidad en Mods).

Comandos de trucos:
  jennikita.botella_estado      -> dice si el script está cargado y enganchado
  jennikita.botella_reiniciar   -> olvida las partidas en curso por si algo
                                   se queda atascado.
"""
import math
import os
import random

import alarms
import services
from date_and_time import create_time_span
import sims4.commands
import sims4.log
import sims4.math
import sims4.resources
from event_testing.results import TestResult
from interactions.context import InteractionContext, QueueInsertStrategy
from interactions.interaction_finisher import FinishingType
from interactions.priority import Priority
from sims.sim_info_types import Age, Species
from sims4.localization import LocalizationHelperTuning
from ui.ui_dialog_notification import UiDialogNotification
from ui.ui_dialog_picker import SimPickerRow, UiSimPicker

_logger_juego = sims4.log.Logger('JennikitaBotella', default_owner='Jennikita')

try:
    _RUTA_LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'jennikita_botella_log.txt')
    with open(_RUTA_LOG, 'w', encoding='utf-8') as _f:
        _f.write('Juego de la botella - registro (v8)\n')
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

ANGULO_FINAL_BOTELLA = 160.0
MEDIA_DISTANCIA_BESO = 0.381
ROMANCE = 16651
PUNTOS_ROMANCE = 10
MAXIMO_JUGADORES = 8
RADIO_ASIENTO = 0.9
RONDAS = 1

# Tiempos en minutos del juego
ESPERA_TURNO_MIN = 2
DURACION_MAXIMA_PARTIDA = 180
MAX_ESPERA_SENTARSE = 60
MAX_DURACION_TURNO = 180

TITULO = 'Juego de la botella'
TEXTO_SIN_PAREJA = ('Tiene que haber otro Sim sentado a jugar alrededor de la botella con quien '
                    'se pueda besar (misma franja de edad y sin ser familia).')
TEXTO_NADIE = 'La botella ha girado… pero no señala a nadie. ¡Hacen falta más jugadores!'
TEXTO_SENALA = '¡La botella de {} señala a {}! Toca beso.'
TEXTO_PLANTON = '{} no ha llegado a tiempo. ¡Otra vez será!'
TEXTO_SELECTOR = 'Elige quién se sienta a jugar alrededor de la botella.'
TEXTO_FIN = '¡Fin del juego! Todos han girado la botella.'
TEXTO_TURNO = 'Le toca girar la botella a {}.'

JUGAR = 'Jennikita:Botella_Jugar'
GIRAR = 'Jennikita:Botella_Girar'
GIRAR_ACCION = 'Jennikita:Botella_Girar_Accion'
ANIMAR = 'Jennikita:Botella_Animar'
SENTARSE = ('Jennikita:Botella_Sentarse_Rodillas', 'Jennikita:Botella_Sentarse_Cruzado')
ESPERAR = ('Jennikita:Botella_Esperar_A', 'Jennikita:Botella_Esperar_B')
BESAR = ('Jennikita:Botella_Besar_A', 'Jennikita:Botella_Besar_B')

_ADULTOS = (Age.YOUNGADULT, Age.ADULT, Age.ELDER)

_PARTIDAS = {}
_SENTADOS = {}
_ANIMADORES = {}
_ASIENTOS = {}
_ENGANCHADAS = []
_JUEGOS = {}
_EN_SITIO = {}


def _fnv64(texto):
    h = 0xCBF29CE484222325
    for c in texto.lower().encode('utf-8'):
        h = h * 0x100000001B3 & 0xFFFFFFFFFFFFFFFF
        h ^= c
    return h


def _id(nombre):
    return _fnv64(nombre) | 0x8000000000000000


_IDS_SENTARSE = frozenset(_id(n) for n in SENTARSE)
_IDS_ESPERAR = frozenset(_id(n) for n in ESPERAR)
_IDS_JUEGO = frozenset(_id(n) for n in SENTARSE + ESPERAR + BESAR + (ANIMAR, GIRAR_ACCION))


def _ahora():
    return services.time_service().sim_now


def _minutos_desde(momento):
    """Minutos del juego que han pasado desde `momento` (un sim_now anterior)."""
    try:
        return (_ahora() - momento).in_minutes()
    except Exception:
        return 0


def _afordancia(nombre):
    gestor = services.get_instance_manager(sims4.resources.Types.INTERACTION)
    return gestor.get(_id(nombre))


def _es(si, ids):
    afordancia = getattr(si, 'affordance', None)
    return getattr(afordancia, 'guid64', None) in ids


def _texto(texto):
    return lambda *_, **__: LocalizationHelperTuning.get_raw_text(texto)


def _aviso(texto):
    try:
        dialogo = UiDialogNotification.TunableFactory().default(None, title=_texto(TITULO),
                                                                 text=_texto(texto))
        dialogo.show_dialog()
    except Exception as e:
        logger.error('No se pudo mostrar el aviso: {}', e)


def _nombre(sim):
    return sim.sim_info.first_name


def _sim(sim_id):
    info = services.sim_info_manager().get(sim_id)
    if info is not None:
        return info.get_sim_instance()
    return None


def _empujar(sim, afordancia, objetivo, prioridad=Priority.High):
    if isinstance(afordancia, str):
        nombre, afordancia = afordancia, _afordancia(afordancia)
        if afordancia is None:
            logger.error('No se encuentra la interacción {}', nombre)
            return False
    contexto = InteractionContext(sim, InteractionContext.SOURCE_SCRIPT, prioridad,
                                  insert_strategy=QueueInsertStrategy.NEXT)
    resultado = sim.push_super_affordance(afordancia, objetivo, contexto)
    if not resultado:
        logger.warn('No se pudo empujar {} a {}: {}', afordancia, sim, resultado)
    else:
        _log('{} -> {}', _nombre(sim), getattr(afordancia, '__name__', afordancia))
    return bool(resultado)


def _cancelar(sim, ids, motivo):
    for si in tuple(sim.si_state or ()):
        if _es(si, ids):
            si.cancel(FinishingType.USER_CANCEL, motivo)


def _mover(sim, posicion, giro, superficie):
    """Coloca al Sim en `posicion` mirando hacia `giro`, a su propia altura."""
    posicion = sims4.math.Vector3(posicion.x, sim.position.y, posicion.z)
    transformacion = sims4.math.Transform(posicion, sims4.math.angle_to_yaw_quaternion(giro))
    sim.location = sims4.math.Location(transformacion, superficie)


def _colocar(sim, partida):
    posicion, giro = partida['sitios'][sim.sim_id]
    _mover(sim, posicion, giro, partida['superficie'])


def _orientar_botella(botella, sim):
    """Gira la botella para que, al acabar la animación, el cuello apunte al Sim."""
    if botella.parent is not None:
        return
    dx = sim.position.x - botella.position.x
    dz = sim.position.z - botella.position.z
    giro = math.atan2(dx, dz) - math.radians(ANGULO_FINAL_BOTELLA)
    transformacion = sims4.math.Transform(botella.position, sims4.math.angle_to_yaw_quaternion(giro))
    botella.location = sims4.math.Location(transformacion, botella.routing_surface)


def _volver_a_sentarse(sim, botella):
    datos = _SENTADOS.get(sim.sim_id)
    if datos is not None and datos[0] == botella.id:
        _empujar(sim, datos[1], botella)


def _franja(info):
    if info.species != Species.HUMAN:
        return None
    if info.age == Age.TEEN:
        return 'adolescente'
    if info.age in _ADULTOS:
        return 'adulto'
    return None


def _familia(a, b):
    prueba = getattr(a, 'incest_prevention_test', None)
    if prueba is not None:
        try:
            return not prueba(b)
        except Exception as e:
            logger.warn('Fallo en incest_prevention_test: {}', e)
    return a.household_id == b.household_id


def _pueden_besarse(a, b):
    if a.sim_id == b.sim_id:
        return False
    franja = _franja(a)
    return franja is not None and franja == _franja(b) and not _familia(a, b)


def _partida(sim_id):
    partida = _PARTIDAS.get(sim_id)
    if partida is not None and _minutos_desde(partida['creada']) > DURACION_MAXIMA_PARTIDA:
        _terminar(partida)
        return None
    return partida


def _terminar(partida):
    for sim_id in (partida['a'], partida['b']):
        if _PARTIDAS.get(sim_id) is partida:
            del _PARTIDAS[sim_id]


def _sentados(botella):
    for sim in tuple(services.sim_info_manager().instanced_sims_gen()):
        for si in tuple(sim.si_state or ()):
            if _es(si, _IDS_SENTARSE) and si.target is botella and not getattr(si, 'is_finishing', False):
                yield sim, si
                break


def _candidatos(actor, botella):
    return [sim for sim, _ in _sentados(botella)
            if sim is not actor
            and _partida(sim.sim_id) is None
            and _pueden_besarse(actor.sim_info, sim.sim_info)]


def _crear_partida(sim, pareja, botella):
    centro = sim.position
    dx = botella.position.x - centro.x
    dz = botella.position.z - centro.z
    largo = math.hypot(dx, dz) or 1.0
    rx, rz = dz / largo, -dx / largo
    m = MEDIA_DISTANCIA_BESO
    pos_a = sims4.math.Vector3(centro.x + rx * m, centro.y, centro.z + rz * m)
    pos_b = sims4.math.Vector3(centro.x - rx * m, centro.y, centro.z - rz * m)
    giro_a = math.atan2(pos_b.x - pos_a.x, pos_b.z - pos_a.z)
    partida = {
        'a': sim.sim_id,
        'b': pareja.sim_id,
        'botella': botella,
        'superficie': sim.routing_surface,
        'sitios': {sim.sim_id: (pos_a, giro_a), pareja.sim_id: (pos_b, giro_a + math.pi)},
        'esperando': {},
        'empezada': False,
        'romance': False,
        'creada': _ahora(),
    }
    _PARTIDAS[sim.sim_id] = partida
    _PARTIDAS[pareja.sim_id] = partida
    return partida


def _en_marcha_o_cola(sim, ids):
    try:
        for si in tuple(sim.si_state or ()):
            if _es(si, ids):
                return True
        for si in tuple(sim.queue):
            if _es(si, ids):
                return True
    except Exception as e:
        _log('No se pudo mirar la cola de {}: {}', _nombre(sim), e)
        return True
    return False


def _empezar_beso(partida):
    _log('Empieza el beso')
    partida['empezada'] = True
    botella = partida['botella']
    a, b = _sim(partida['a']), _sim(partida['b'])
    if a is None or b is None:
        _terminar(partida)
        return
    _empujar(a, BESAR[0], botella)
    _empujar(b, BESAR[1], botella)
    for si in tuple(partida['esperando'].values()):
        si.cancel(FinishingType.NATURAL, 'Empieza el beso')
    for sim, si in list(_sentados(botella)):
        if sim.sim_id in (partida['a'], partida['b']):
            continue
        _ANIMADORES[sim.sim_id] = botella.id
        si.cancel(FinishingType.USER_CANCEL, 'Animar el beso')
        _empujar(sim, ANIMAR, botella)


def _jugables(actor):
    """Sims que se pueden sentar a jugar: humanos de adolescente en adelante."""
    sims = [sim for sim in services.sim_info_manager().instanced_sims_gen()
            if _franja(sim.sim_info) is not None]
    sims.sort(key=lambda s: (s is not actor,
                             s.sim_info.household_id != actor.sim_info.household_id,
                             _nombre(s)))
    return sims


def _esta_sentado(sim, botella):
    return any(s is sim for s, _ in _sentados(botella))


def _sumar_romance(partida):
    pista = services.get_instance_manager(sims4.resources.Types.STATISTIC).get(ROMANCE)
    a = services.sim_info_manager().get(partida['a'])
    if pista is not None and a is not None:
        a.relationship_tracker.add_relationship_score(partida['b'], PUNTOS_ROMANCE, pista)


def _sim_del_contexto(context):
    if context is not None:
        return context.sim
    return None


def _angulo(botella, posicion):
    return math.atan2(posicion.x - botella.position.x, posicion.z - botella.position.z)


def _diferencia(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def _repartir_asientos(botella, nuevos):
    """Reparte a todos los jugadores en círculo, a la misma distancia entre sí.
    Los que ya están sentados se quedan donde están; a cada Sim nuevo le toca
    el hueco libre más cercano a donde está ahora, para que camine lo menos posible."""
    if not nuevos:
        return
    sentados = [s for s, _ in _sentados(botella) if s not in nuevos]
    total = len(sentados) + len(nuevos)
    paso = 2 * math.pi / total
    base = _angulo(botella, (sentados or nuevos)[0].position)
    libres = [base + i * paso for i in range(total)]
    for sim in sentados:
        angulo = _angulo(botella, sim.position)
        libres.remove(min(libres, key=lambda a: _diferencia(a, angulo)))
    for sim in sorted(nuevos, key=lambda s: _angulo(botella, s.position)):
        angulo = _angulo(botella, sim.position)
        hueco = min(libres, key=lambda a: _diferencia(a, angulo))
        libres.remove(hueco)
        c = botella.position
        posicion = sims4.math.Vector3(c.x + RADIO_ASIENTO * math.sin(hueco), c.y,
                                      c.z + RADIO_ASIENTO * math.cos(hueco))
        _ASIENTOS[sim.sim_id] = (botella.id, posicion, hueco + math.pi)


def _asiento(sim, botella):
    datos = _ASIENTOS.get(sim.sim_id)
    if datos is not None and botella is not None and datos[0] == botella.id:
        return datos
    return None


def _ir_al_asiento(sim, botella):
    datos = _asiento(sim, botella)
    if datos is None:
        return
    _mover(sim, datos[1], datos[2], sim.routing_surface)


def _preparar_juego(actor, botella, nuevos):
    juego = _JUEGOS.get(botella.id)
    if juego is None:
        juego = {'botella': botella, 'orden': [], 'turno': 0, 'en_turno': False,
                 'desde': _ahora(), 'turno_desde': _ahora(), 'alarma': None}
        _JUEGOS[botella.id] = juego
    for sim in nuevos:
        if sim.sim_id not in juego['orden']:
            juego['orden'].append(sim.sim_id)

    def angulo(sim_id):
        datos = _ASIENTOS.get(sim_id)
        if datos is not None:
            return datos[2]
        return 0.0

    base = angulo(actor.sim_id) if actor.sim_id in juego['orden'] else 0.0
    pendientes = juego['orden'][juego['turno']:]
    pendientes.sort(key=lambda sid: (angulo(sid) - base) % (2 * math.pi))
    juego['orden'] = juego['orden'][:juego['turno']] + pendientes * RONDAS
    juego['desde'] = _ahora()
    _log('Juego preparado: {} jugadores', len(set(juego['orden'])))


def _programar_turno(botella, minutos=ESPERA_TURNO_MIN):
    juego = _JUEGOS.get(botella.id)
    if juego is None:
        return
    try:
        if juego.get('alarma') is not None:
            alarms.cancel_alarm(juego['alarma'])
        juego['alarma'] = alarms.add_alarm(botella, create_time_span(minutes=minutos),
                                           lambda _handle: _comprobar_turno(botella))
    except Exception as e:
        logger.warn('No se pudo programar el turno, se comprueba ya: {}', e)
        _comprobar_turno(botella)


def _fin_de_turno(botella):
    juego = _JUEGOS.get(botella.id)
    if juego is None:
        return
    juego['en_turno'] = False
    _log('Fin del turno')
    _programar_turno(botella)


def _terminar_juego(botella, motivo):
    juego = _JUEGOS.pop(botella.id, None)
    if juego is None:
        return
    _log('Fin del juego: {}', motivo)
    try:
        if juego.get('alarma') is not None:
            alarms.cancel_alarm(juego['alarma'])
    except Exception:
        pass
    _aviso(TEXTO_FIN)
    for sim_id in set(juego['orden']):
        sim = _sim(sim_id)
        if sim is not None:
            _cancelar(sim, _IDS_SENTARSE, 'Fin del juego')


def _comprobar_turno(botella):
    try:
        juego = _JUEGOS.get(botella.id)
        if juego is None:
            return
        juego['alarma'] = None
        if juego['en_turno']:
            if _minutos_desde(juego['turno_desde']) > MAX_DURACION_TURNO:
                _log('El turno se ha alargado demasiado: se pasa al siguiente')
                juego['en_turno'] = False
            else:
                _programar_turno(botella, 10)
                return
        sentados = {sid for sid, bid in _EN_SITIO.items() if bid == botella.id}
        pendientes = []
        for sid in set(juego['orden']):
            if sid in sentados:
                continue
            sim = _sim(sid)
            if sim is not None and _en_marcha_o_cola(sim, _IDS_JUEGO):
                pendientes.append(sid)
        if pendientes and _minutos_desde(juego['desde']) < MAX_ESPERA_SENTARSE:
            _programar_turno(botella, 5)
            return
        while juego['turno'] < len(juego['orden']):
            sid = juego['orden'][juego['turno']]
            juego['turno'] += 1
            sim = _sim(sid)
            if sim is None or sid not in sentados:
                _log('Se salta el turno de un jugador que no está sentado')
                continue
            if not _candidatos(sim, botella):
                _log('{} no tiene con quién besarse: se salta su turno', _nombre(sim))
                continue
            juego['en_turno'] = True
            juego['turno_desde'] = _ahora()
            juego['desde'] = _ahora()
            _log('Turno de {}', _nombre(sim))
            _aviso(TEXTO_TURNO.format(_nombre(sim)))
            _cancelar(sim, _IDS_SENTARSE, 'Le toca girar')
            if _empujar(sim, GIRAR_ACCION, botella):
                _programar_turno(botella, 10)
                return
            juego['en_turno'] = False
        _terminar_juego(botella, 'ronda completa')
    except Exception as e:
        logger.error('Error al pasar el turno: {}', e)


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
        nuevos = []
        try:
            for info in dialogo.get_result_tags():
                sim = info.get_sim_instance()
                if sim is not None and not _esta_sentado(sim, botella):
                    nuevos.append(sim)
            _repartir_asientos(botella, nuevos)
            for sim in nuevos:
                _empujar(sim, random.choice(SENTARSE), botella)
            _preparar_juego(actor, botella, nuevos)
        except Exception as e:
            logger.error('Error al sentar a los jugadores: {}', e)

    dialogo.add_listener(_elegidos)
    dialogo.show_dialog()


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
        try:
            _SENTADOS[self.sim.sim_id] = (self.target.id, self.affordance)
            _EN_SITIO[self.sim.sim_id] = self.target.id
            _ir_al_asiento(self.sim, self.target)
            _log('{} se sienta', _nombre(self.sim))
            _programar_turno(self.target)
        except Exception as e:
            logger.error('Error al sentarse: {}', e)
        try:
            result = yield from original(self, timeline)
        finally:
            if _EN_SITIO.get(self.sim.sim_id) == self.target.id:
                del _EN_SITIO[self.sim.sim_id]
        return result

    return _run_interaction_gen


def _hacer_test_girar(original):

    def _test(cls, target, context, **kwargs):
        result = original(target, context, **kwargs)
        if not result:
            return result
        sim = _sim_del_contexto(context)
        if sim is None or target is None:
            return result
        try:
            if _partida(sim.sim_id) is not None:
                return TestResult(False, 'Ya está en una partida')
            if not _candidatos(sim, target):
                return TestResult(False, 'Sin pareja', tooltip=_texto(TEXTO_SIN_PAREJA))
        except Exception as e:
            logger.error('Error en el test de girar la botella: {}', e)
        return TestResult.TRUE

    return classmethod(_test)


def _al_parar(sim, pareja, botella):
    if (pareja is None or pareja.sim_info.get_sim_instance() is None
            or _partida(pareja.sim_id) is not None
            or not _pueden_besarse(sim.sim_info, pareja.sim_info)):
        _aviso(TEXTO_NADIE)
        _volver_a_sentarse(sim, botella)
        _fin_de_turno(botella)
        return
    _log('La botella de {} señala a {}', _nombre(sim), _nombre(pareja))
    _aviso(TEXTO_SENALA.format(_nombre(sim), _nombre(pareja)))
    _crear_partida(sim, pareja, botella)
    _cancelar(pareja, _IDS_SENTARSE, 'Le ha tocado la botella')
    _empujar(sim, ESPERAR[0], botella)
    _empujar(pareja, ESPERAR[1], botella)


def _hacer_run_girar_menu(original):

    def _run_interaction_gen(self, timeline):
        try:
            _cancelar(self.sim, _IDS_SENTARSE, 'Va a girar la botella')
            _empujar(self.sim, GIRAR_ACCION, self.target, Priority.High)
        except Exception as e:
            logger.error('Error al mandar a girar la botella: {}', e)
        result = yield from original(self, timeline)
        return result

    return _run_interaction_gen


def _hacer_run_girar(original):

    def _run_interaction_gen(self, timeline):
        pareja = None
        try:
            candidatos = _candidatos(self.sim, self.target)
            if candidatos:
                pareja = random.choice(candidatos)
                _orientar_botella(self.target, pareja)
        except Exception as e:
            logger.error('Error al preparar el giro: {}', e)
        result = yield from original(self, timeline)
        if result is not False:
            try:
                _al_parar(self.sim, pareja, self.target)
            except Exception as e:
                logger.error('Error al parar la botella: {}', e)
                _fin_de_turno(self.target)
        else:
            _log('El giro de {} no se ha completado', _nombre(self.sim))
            _volver_a_sentarse(self.sim, self.target)
            _fin_de_turno(self.target)
        return result

    return _run_interaction_gen


def _hacer_test_partida(original):

    def _test(cls, target, context, **kwargs):
        sim = _sim_del_contexto(context)
        if sim is None or _partida(sim.sim_id) is None:
            return TestResult(False, 'Sin partida de la botella')
        return original(target, context, **kwargs)

    return classmethod(_test)


def _hacer_run_esperar(original):

    def _run_interaction_gen(self, timeline):
        partida = _partida(self.sim.sim_id)
        if partida is not None and not partida['empezada']:
            try:
                _colocar(self.sim, partida)
                partida['esperando'][self.sim.sim_id] = self
                _log('{} espera el beso ({} de 2)', _nombre(self.sim), len(partida['esperando']))
                if len(partida['esperando']) == 2:
                    _empezar_beso(partida)
                else:
                    es_a = self.sim.sim_id == partida['a']
                    otro = _sim(partida['b'] if es_a else partida['a'])
                    if otro is not None and not _en_marcha_o_cola(otro, _IDS_ESPERAR):
                        _log('{} no tenía la espera en cola: se le vuelve a mandar', _nombre(otro))
                        _cancelar(otro, _IDS_SENTARSE, 'Le ha tocado la botella')
                        _empujar(otro, ESPERAR[1] if es_a else ESPERAR[0], partida['botella'])
            except Exception as e:
                logger.error('Error al esperar el beso: {}', e)
        result = yield from original(self, timeline)
        if partida is not None and not partida['empezada']:
            _log('Termina la espera de {} sin beso', _nombre(self.sim))
            try:
                _terminar(partida)
                otro = _sim(partida['b'] if self.sim.sim_id == partida['a'] else partida['a'])
                if otro is not None:
                    _aviso(TEXTO_PLANTON.format(_nombre(otro)))
                _volver_a_sentarse(self.sim, partida['botella'])
                if not partida.get('turno_cerrado'):
                    partida['turno_cerrado'] = True
                    _fin_de_turno(partida['botella'])
            except Exception as e:
                logger.error('Error al cancelar la espera: {}', e)
        return result

    return _run_interaction_gen


def _hacer_run_besar(original):

    def _run_interaction_gen(self, timeline):
        partida = _partida(self.sim.sim_id)
        if partida is not None:
            try:
                _colocar(self.sim, partida)
            except Exception as e:
                logger.error('Error al colocar para el beso: {}', e)
        result = yield from original(self, timeline)
        if partida is not None:
            try:
                if result is not False and not partida['romance']:
                    partida['romance'] = True
                    _sumar_romance(partida)
                if _PARTIDAS.get(self.sim.sim_id) is partida:
                    del _PARTIDAS[self.sim.sim_id]
                _volver_a_sentarse(self.sim, partida['botella'])
                partida['besos_hechos'] = partida.get('besos_hechos', 0) + 1
                if partida['besos_hechos'] >= 2 and not partida.get('turno_cerrado'):
                    partida['turno_cerrado'] = True
                    _log('Termina el beso')
                    _fin_de_turno(partida['botella'])
            except Exception as e:
                logger.error('Error al acabar el beso: {}', e)
        return result

    return _run_interaction_gen


def _hacer_test_animar(original):

    def _test(cls, target, context, **kwargs):
        sim = _sim_del_contexto(context)
        if sim is None or target is None or _ANIMADORES.get(sim.sim_id) != target.id:
            return TestResult(False, 'No está animando')
        return original(target, context, **kwargs)

    return classmethod(_test)


def _hacer_run_animar(original):

    def _run_interaction_gen(self, timeline):
        result = yield from original(self, timeline)
        try:
            _ANIMADORES.pop(self.sim.sim_id, None)
            _volver_a_sentarse(self.sim, self.target)
        except Exception as e:
            logger.error('Error al acabar de animar: {}', e)
        return result

    return _run_interaction_gen


_COMPORTAMIENTOS = [
    ((JUGAR,), None, _hacer_run_jugar),
    (SENTARSE, None, _hacer_run_sentarse),
    ((GIRAR,), _hacer_test_girar, _hacer_run_girar_menu),
    ((GIRAR_ACCION,), _hacer_test_girar, _hacer_run_girar),
    (ESPERAR, _hacer_test_partida, _hacer_run_esperar),
    (BESAR, _hacer_test_partida, _hacer_run_besar),
    ((ANIMAR,), _hacer_test_animar, _hacer_run_animar),
]


def _enganchar(gestor=None):
    if gestor is None:
        gestor = services.get_instance_manager(sims4.resources.Types.INTERACTION)
    for nombres, hacer_test, hacer_run in _COMPORTAMIENTOS:
        for nombre in nombres:
            try:
                clase = gestor.get(_id(nombre))
                if clase is None:
                    logger.error('No se ha cargado el tuning {}', nombre)
                    continue
                if getattr(clase, '_jennikita_botella', False):
                    continue
                if hacer_test is not None:
                    clase._test = hacer_test(clase._test)
                clase._run_interaction_gen = hacer_run(clase._run_interaction_gen)
                clase._jennikita_botella = True
                _ENGANCHADAS.append(nombre)
            except Exception as e:
                logger.error('No se pudo enganchar {}: {}', nombre, e)


try:
    services.get_instance_manager(sims4.resources.Types.INTERACTION).add_on_load_complete(_enganchar)
except Exception as _e:
    logger.error('No se pudo registrar el enganche: {}', _e)


@sims4.commands.Command('jennikita.botella_estado', command_type=sims4.commands.CommandType.Live)
def _cmd_estado(_connection=None):
    sims4.commands.output('Juego de la botella v8: script cargado. Interacciones enganchadas: {} de 10.'
                          .format(len(_ENGANCHADAS)), _connection)
    for nombre in _ENGANCHADAS:
        sims4.commands.output('  - ' + nombre, _connection)


@sims4.commands.Command('jennikita.botella_reiniciar', command_type=sims4.commands.CommandType.Live)
def _cmd_reiniciar(_connection=None):
    n = len(set(map(id, _PARTIDAS.values())))
    _PARTIDAS.clear()
    _ANIMADORES.clear()
    _ASIENTOS.clear()
    for juego in list(_JUEGOS.values()):
        try:
            if juego.get('alarma') is not None:
                alarms.cancel_alarm(juego['alarma'])
        except Exception:
            pass
    _JUEGOS.clear()
    _EN_SITIO.clear()
    sims4.commands.output('Juego de la botella reiniciado: {} partidas olvidadas.'.format(n), _connection)
