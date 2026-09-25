"""
Juego de la botella - Jennikita

Interacciones de la botella (el tuning está en el .package):
  - Sentarse a jugar (de rodillas / piernas cruzadas): el Sim se sienta en el
    círculo alrededor de la botella. Solo los Sims sentados pueden salir.
  - Girar la botella: se elige al azar un Sim sentado con el que el Sim que
    gira pueda besarse, se orienta la botella para que acabe apuntándole, se
    reproduce el giro y después los dos se colocan uno frente al otro y se
    besan. El resto de Sims sentados animan y luego vuelven a sentarse.

Quién puede besarse: adolescentes con adolescentes, y jóvenes adultos,
adultos y ancianos entre sí. Nunca niños ni familiares.

Las animaciones de Love4Sims se han centrado en el origen, así que es este
script el que coloca a cada Sim en su sitio antes del beso.

Compilar con Python 3.7 y meter el .pyc en un zip renombrado a
jennikita_botella.ts4script (máximo una carpeta de profundidad en Mods).

Comando de trucos: jennikita.botella_reiniciar  -> olvida las partidas en
curso por si algo se queda atascado.
"""
import math
import random
import time

import services
import sims4.commands
import sims4.log
import sims4.math
import sims4.resources
from event_testing.results import TestResult
from interactions.base.super_interaction import SuperInteraction
from interactions.context import InteractionContext, QueueInsertStrategy
from interactions.interaction_finisher import FinishingType
from interactions.priority import Priority
from sims.sim_info_types import Age, Species
from sims4.localization import LocalizationHelperTuning
from sims4.tuning.tunable import Tunable
from ui.ui_dialog_notification import UiDialogNotification

logger = sims4.log.Logger('JennikitaBotella', default_owner='Jennikita')

# Hacia dónde apunta el cuello de la botella al acabar la animación de giro,
# en grados, medido en el espacio del objeto (sale del clip de Love4Sims).
ANGULO_FINAL_BOTELLA = 113.7
# En el clip del beso los dos Sims están a 0,762 m, mirándose.
MEDIA_DISTANCIA_BESO = 0.381
# Una partida que no ha acabado en este tiempo se da por perdida.
DURACION_MAXIMA_PARTIDA = 180.0

ROMANCE = 16651  # LTR_Romance_Main
PUNTOS_ROMANCE = 10

TITULO = 'Juego de la botella'
TEXTO_SIN_PAREJA = ('Tiene que haber otro Sim sentado a jugar alrededor de la botella '
                    'con quien se pueda besar (misma franja de edad y sin ser familia).')
TEXTO_NADIE = 'La botella ha girado… pero no señala a nadie. ¡Hacen falta más jugadores!'
TEXTO_SENALA = '¡La botella de {} señala a {}! Toca beso.'
TEXTO_PLANTON = '{} no ha llegado a tiempo. ¡Otra vez será!'

_ADULTOS = (Age.YOUNGADULT, Age.ADULT, Age.ELDER)

# sim_id -> partida en curso (la comparten los dos Sims que se besan)
_PARTIDAS = {}
# sim_id -> (id de la botella, afordancia con la que se sentó)
_SENTADOS = {}
# sim_id -> id de la botella en la que está animando
_ANIMADORES = {}


# --- Utilidades --------------------------------------------------------------

def _fnv64(texto):
    h = 0xCBF29CE484222325
    for c in texto.lower().encode('utf-8'):
        h = ((h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF) ^ c
    return h


def _afordancia(nombre):
    gestor = services.get_instance_manager(sims4.resources.Types.INTERACTION)
    return gestor.get(_fnv64(nombre) | (1 << 63))


def _texto(texto):
    return lambda *_, **__: LocalizationHelperTuning.get_raw_text(texto)


def _aviso(texto):
    try:
        dialogo = UiDialogNotification.TunableFactory().default(
            None, title=_texto(TITULO), text=_texto(texto))
        dialogo.show_dialog()
    except Exception as e:
        logger.error('No se pudo mostrar el aviso: {}', e)


def _nombre(sim):
    return sim.sim_info.first_name


def _sim(sim_id):
    info = services.sim_info_manager().get(sim_id)
    return info.get_sim_instance() if info is not None else None


def _empujar(sim, afordancia, objetivo):
    if isinstance(afordancia, str):
        nombre, afordancia = afordancia, _afordancia(afordancia)
        if afordancia is None:
            logger.error('No se encuentra la interacción {}', nombre)
            return False
    contexto = InteractionContext(sim, InteractionContext.SOURCE_SCRIPT, Priority.High,
                                  insert_strategy=QueueInsertStrategy.NEXT)
    resultado = sim.push_super_affordance(afordancia, objetivo, contexto)
    if not resultado:
        logger.warn('No se pudo empujar {} a {}: {}', afordancia, sim, resultado)
    return bool(resultado)


def _cancelar(sim, clase, motivo):
    for si in tuple(sim.si_state or ()):
        if isinstance(si, clase):
            si.cancel(FinishingType.USER_CANCEL, motivo)


def _colocar(sim, partida):
    posicion, giro = partida['sitios'][sim.sim_id]
    transformacion = sims4.math.Transform(posicion, sims4.math.angle_to_yaw_quaternion(giro))
    sim.location = sims4.math.Location(transformacion, partida['superficie'])


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


# --- Quién puede besarse ----------------------------------------------------

def _franja(info):
    if info.species != Species.HUMAN:
        return None
    if info.age == Age.TEEN:
        return 'adolescente'
    if info.age in _ADULTOS:
        return 'adulto'
    return None


def _familia(a, b):
    comprobado = False
    try:
        prueba = getattr(a, 'incest_prevention_test', None)
        if prueba is not None:
            comprobado = True
            if not prueba(b):
                return True
    except Exception as e:
        logger.warn('Fallo en incest_prevention_test: {}', e)
    try:
        arbol = getattr(a, '_genealogy_tracker', None)
        if arbol is not None:
            comprobado = True
            if b.sim_id in set(arbol.get_family_sim_ids()):
                return True
    except Exception as e:
        logger.warn('Fallo al leer el árbol genealógico: {}', e)
    if not comprobado:
        # Sin forma de saberlo, mejor no emparejar a gente de la misma casa.
        return a.household_id == b.household_id
    return False


def _pueden_besarse(a, b):
    if a.sim_id == b.sim_id:
        return False
    franja = _franja(a)
    return franja is not None and franja == _franja(b) and not _familia(a, b)


def _partida(sim_id):
    partida = _PARTIDAS.get(sim_id)
    if partida is not None and time.monotonic() - partida['creada'] > DURACION_MAXIMA_PARTIDA:
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
            if isinstance(si, BotellaSentarseInteraction) and si.target is botella \
                    and not getattr(si, 'is_finishing', False):
                yield sim, si
                break


def _candidatos(actor, botella):
    return [sim for sim, _ in _sentados(botella)
            if sim is not actor and _partida(sim.sim_id) is None
            and _pueden_besarse(actor.sim_info, sim.sim_info)]


def _crear_partida(sim, pareja, botella):
    centro = sim.position
    dx = botella.position.x - centro.x
    dz = botella.position.z - centro.z
    largo = math.hypot(dx, dz) or 1.0
    # Los dos se ponen a los lados del sitio desde el que se giró la botella.
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
        'creada': time.monotonic(),
    }
    _PARTIDAS[sim.sim_id] = partida
    _PARTIDAS[pareja.sim_id] = partida
    return partida


def _empezar_beso(partida):
    partida['empezada'] = True
    botella = partida['botella']
    a, b = _sim(partida['a']), _sim(partida['b'])
    if a is None or b is None:
        _terminar(partida)
        return
    _empujar(a, 'Jennikita:Botella_Besar_A', botella)
    _empujar(b, 'Jennikita:Botella_Besar_B', botella)
    for si in tuple(partida['esperando'].values()):
        si.cancel(FinishingType.NATURAL, 'Empieza el beso')
    for sim, si in list(_sentados(botella)):
        if sim.sim_id in (partida['a'], partida['b']):
            continue
        _ANIMADORES[sim.sim_id] = botella.id
        si.cancel(FinishingType.USER_CANCEL, 'Animar el beso')
        _empujar(sim, 'Jennikita:Botella_Animar', botella)


# --- Interacciones ------------------------------------------------------------

class BotellaSentarseInteraction(SuperInteraction):

    def _run_interaction_gen(self, timeline):
        try:
            _SENTADOS[self.sim.sim_id] = (self.target.id, self.affordance)
        except Exception as e:
            logger.error('Error al sentarse: {}', e)
        result = yield from super()._run_interaction_gen(timeline)
        return result


class BotellaGirarInteraction(SuperInteraction):

    @classmethod
    def _test(cls, target, context, **kwargs):
        result = super()._test(target, context, **kwargs)
        if not result:
            return result
        sim = context.sim if context is not None else None
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

    def _run_interaction_gen(self, timeline):
        self._pareja = None
        try:
            candidatos = _candidatos(self.sim, self.target)
            if candidatos:
                self._pareja = random.choice(candidatos)
                _orientar_botella(self.target, self._pareja)
        except Exception as e:
            logger.error('Error al preparar el giro: {}', e)
        result = yield from super()._run_interaction_gen(timeline)
        if result is not False:
            try:
                self._al_parar()
            except Exception as e:
                logger.error('Error al parar la botella: {}', e)
        return result

    def _al_parar(self):
        sim, pareja, botella = self.sim, self._pareja, self.target
        if pareja is None or pareja.sim_info.get_sim_instance() is None \
                or _partida(pareja.sim_id) is not None \
                or not _pueden_besarse(sim.sim_info, pareja.sim_info):
            _aviso(TEXTO_NADIE)
            return
        _aviso(TEXTO_SENALA.format(_nombre(sim), _nombre(pareja)))
        _crear_partida(sim, pareja, botella)
        _cancelar(pareja, BotellaSentarseInteraction, 'Le ha tocado la botella')
        _empujar(sim, 'Jennikita:Botella_Esperar_A', botella)
        _empujar(pareja, 'Jennikita:Botella_Esperar_B', botella)


class _BotellaPartidaInteraction(SuperInteraction):
    """Interacciones que solo tienen sentido dentro de una partida (se ocultan si no)."""
    INSTANCE_TUNABLES = {
        'rol': Tunable(description='A: el Sim que gira. B: el Sim señalado.',
                       tunable_type=str, default='A'),
    }

    @classmethod
    def _test(cls, target, context, **kwargs):
        sim = context.sim if context is not None else None
        if sim is None or _partida(sim.sim_id) is None:
            return TestResult(False, 'Sin partida de la botella')
        return super()._test(target, context, **kwargs)


class BotellaEsperarInteraction(_BotellaPartidaInteraction):

    def _run_interaction_gen(self, timeline):
        partida = _partida(self.sim.sim_id)
        if partida is not None and not partida['empezada']:
            try:
                _colocar(self.sim, partida)
                partida['esperando'][self.sim.sim_id] = self
                if len(partida['esperando']) == 2:
                    _empezar_beso(partida)
            except Exception as e:
                logger.error('Error al esperar el beso: {}', e)
        result = yield from super()._run_interaction_gen(timeline)
        if partida is not None and not partida['empezada']:
            _terminar(partida)
            otro = _sim(partida['b'] if self.sim.sim_id == partida['a'] else partida['a'])
            if otro is not None:
                _aviso(TEXTO_PLANTON.format(_nombre(otro)))
            _volver_a_sentarse(self.sim, partida['botella'])
        return result


class BotellaBesarInteraction(_BotellaPartidaInteraction):

    def _run_interaction_gen(self, timeline):
        partida = _partida(self.sim.sim_id)
        if partida is not None:
            try:
                _colocar(self.sim, partida)
            except Exception as e:
                logger.error('Error al colocar para el beso: {}', e)
        result = yield from super()._run_interaction_gen(timeline)
        if partida is not None:
            try:
                if result is not False and not partida['romance']:
                    partida['romance'] = True
                    self._sumar_romance(partida)
                if _PARTIDAS.get(self.sim.sim_id) is partida:
                    del _PARTIDAS[self.sim.sim_id]
                _volver_a_sentarse(self.sim, partida['botella'])
            except Exception as e:
                logger.error('Error al acabar el beso: {}', e)
        return result

    @staticmethod
    def _sumar_romance(partida):
        pista = services.get_instance_manager(sims4.resources.Types.STATISTIC).get(ROMANCE)
        a = services.sim_info_manager().get(partida['a'])
        if pista is not None and a is not None:
            a.relationship_tracker.add_relationship_score(partida['b'], PUNTOS_ROMANCE, pista)


class BotellaAnimarInteraction(SuperInteraction):

    @classmethod
    def _test(cls, target, context, **kwargs):
        sim = context.sim if context is not None else None
        if sim is None or target is None or _ANIMADORES.get(sim.sim_id) != target.id:
            return TestResult(False, 'No está animando')
        return super()._test(target, context, **kwargs)

    def _run_interaction_gen(self, timeline):
        result = yield from super()._run_interaction_gen(timeline)
        try:
            _ANIMADORES.pop(self.sim.sim_id, None)
            _volver_a_sentarse(self.sim, self.target)
        except Exception as e:
            logger.error('Error al acabar de animar: {}', e)
        return result


@sims4.commands.Command('jennikita.botella_reiniciar', command_type=sims4.commands.CommandType.Live)
def _cmd_reiniciar(_connection=None):
    n = len(set(map(id, _PARTIDAS.values())))
    _PARTIDAS.clear()
    _ANIMADORES.clear()
    sims4.commands.output('Juego de la botella reiniciado: {} partidas olvidadas.'.format(n), _connection)
