"""Camion de la basura funcional (Jennikita) para Los Sims 4.

Script del mod Jennikita_CamionBasura. Necesita el Jennikita_CamionBasura.package.
Se compila con Python 3.7 (la version del juego): ver herramientas/compilar_basurero.py.
"""
import math
import os
import functools
import traceback
import services
import sims4.commands
import sims4.math
import alarms
import date_and_time

SITUACION_BASURERO = 13099760879294426362
CAMION_DEF = 11228603329359746950
BOLSA_DEF = 22174
SONIDO_LLEGADA = 4448119419397510525
SONIDO_TRABAJANDO = 544368327340296755
ESTADO_VOLCADO = 15354
MULTA = 20
MONO_AMARILLO = 17202976458925047176
MONOS_VIEJOS = (16040913242264747554, 10409532022171504658)
INTERACCION_BUSCAR_CUBO = 11856208779766024785
INTERACCION_COGER_BOLSA = 16573961949371287202
HORA_AVISO = 21
HORA_VISITA = 22
ICONO_AVISO = 15318465186728577223
# Interacciones con el basurero (las crea herramientas/basurero_interacciones.py)
INTERACCION_SALUDAR = 15214809009877301499
INTERACCION_RECICLAJE = 11109812326371183564
BUFF_BASURERO_SIMPATICO = 13547429730650624046
ICONO_RECICLAJE = 10213119247726398749
OBJETO_SIM = 14965
AMISTAD_SALUDAR = 5
AMISTAD_RECICLAJE = 3
CONSEJOS_RECICLAJE = (
    "Aclara los envases antes de tirarlos: así no huelen ni atraen bichos.",
    "El papel y el cartón, doblados y sin restos de comida, al contenedor azul.",
    "Las latas, las botellas de plástico y los briks van al contenedor amarillo.",
    "El vidrio va al contenedor verde, pero sin tapones: esos van al amarillo.",
    "Las pilas nunca a la basura normal: llévalas a un punto de recogida.",
    "Los restos de comida y de las plantas sirven para hacer compost en el jardín.",
    "Si el cubo está lleno, no dejes bolsas por el suelo o te caerá una multa.",
    "Reutilizar también cuenta: un tarro de cristal es un bote de galletas estupendo.",
)

DISTANCIA_A_LO_LARGO = 8.0
DISTANCIA_HACIA_CALLE = 5.5
GIRO_EXTRA_GRADOS = 0.0

# Con la bolsa en la mano, espera a que termine la animacion de cogerla, y como mucho
# estos minutos, antes de irse.
MINUTOS_MAX_COGIENDO_BOLSA = 6
# Minutos como mucho que el basurero pasa en el solar antes de irse.
MINUTOS_MAX_VISITA = 20
# Minutos que se queda el camion despues de que se vaya el basurero.
MINUTOS_CAMION_TRAS_IRSE = 5
# Minutos de margen para que el basurero salga andando del solar antes de quitarlo.
MINUTOS_PARA_IRSE = 15

_AJUSTE = {'calle': DISTANCIA_HACIA_CALLE, 'largo': DISTANCIA_A_LO_LARGO, 'giro': GIRO_EXTRA_GRADOS}

_estado = {
    'retirar': None,
    'mono': {},
    'empujados': set(),
    'dia_aviso': -1,
    'dia_visita': -1,
    'camion': None,
    'multa_pendiente': False,
    'entregado': False,
    'fin': None,
    'alarma': None,
    'bolsas_previas': set(),
    'con_bolsa': {},
    'minutos': 0,
}


def _carpeta_log():
    try:
        ruta = os.path.abspath(__file__)
        while ruta and not ruta.lower().endswith(".ts4script"):
            nueva = os.path.dirname(ruta)
            if nueva == ruta:
                break
            ruta = nueva
        if ruta.lower().endswith(".ts4script"):
            return os.path.dirname(ruta)
    except Exception:
        pass
    return os.path.expanduser("~")


def _log(msg):
    try:
        with open((os.path.join(_carpeta_log(), "Jennikita_Basura_log.txt")), "a", encoding="utf-8") as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass


def _notificar(titulo, texto):
    try:
        from ui.ui_dialog_notification import UiDialogNotification
        from sims4.localization import LocalizationHelperTuning
        n = UiDialogNotification.TunableFactory().default((services.get_active_sim()),
          text=(lambda *a, **k: LocalizationHelperTuning.get_raw_text(texto)),
          title=(lambda *a, **k: LocalizationHelperTuning.get_raw_text(titulo)))
        n.show_dialog()
    except Exception:
        _log(traceback.format_exc())


def _sonido(obj, sonido):
    try:
        from audio.primitive import PlaySound
        PlaySound(obj, sonido).start()
    except Exception:
        _log(traceback.format_exc())


def _situacion():
    sm = services.get_zone_situation_manager()
    if sm is None:
        return
    for s in list(sm.running_situations()):
        if getattr(s, "guid64", 0) == SITUACION_BASURERO:
            return s


def _punto_llegada():
    zona = services.current_zone()
    sp = getattr(zona, "active_lot_arrival_spawn_point", None)
    if sp is None:
        return (None, None)
    return (sp.get_approximate_center(), sp.routing_surface)


def _crear_camion():
    (centro, superficie) = _punto_llegada()
    if centro is None:
        _log("Sin punto de llegada: no se pone camion")
        return
    from objects.system import create_object
    import terrain
    lote = services.active_lot()
    lc = getattr(lote, "center", None) or lote.position
    fuera = sims4.math.Vector3(centro.x - lc.x, 0, centro.z - lc.z)
    largo = math.sqrt(fuera.x * fuera.x + fuera.z * fuera.z) or 1.0
    fuera = sims4.math.Vector3(fuera.x / largo, 0, fuera.z / largo)
    a_lo_largo = sims4.math.Vector3(-fuera.z, 0, fuera.x)
    x = centro.x + a_lo_largo.x * _AJUSTE["largo"] + fuera.x * _AJUSTE["calle"]
    z = centro.z + a_lo_largo.z * _AJUSTE["largo"] + fuera.z * _AJUSTE["calle"]
    try:
        y = terrain.get_terrain_height(x, z, superficie)
    except Exception:
        y = centro.y

    angulo = math.atan2(a_lo_largo.x, a_lo_largo.z) + math.radians(_AJUSTE["giro"])
    orientacion = sims4.math.angle_to_yaw_quaternion(angulo)
    camion = create_object(CAMION_DEF)
    if camion is None:
        _log("No se pudo crear el camion (falta el package del camion?)")
        return
    camion.location = sims4.math.Location(sims4.math.Transform(sims4.math.Vector3(x, y, z), orientacion), superficie)
    return camion


def _borrar_camiones():
    om = services.object_manager()
    for o in list(om.get_all()):
        if getattr(getattr(o, "definition", None), "id", None) == CAMION_DEF:
            try:
                o.destroy(source=o, cause="Jennikita: fin del camion de la basura")
            except Exception:
                _log(traceback.format_exc())

    _estado["camion"] = None


def _hay_problemas():
    """Cubo de fuera volcado o bolsas/montones de basura tirados por el suelo del solar."""
    try:
        from sims4.resources import Types
        volcado = services.get_instance_manager(Types.OBJECT_STATE).get(ESTADO_VOLCADO)
        lote = services.active_lot()
        for o in list(services.object_manager().get_all()):
            if volcado is not None and hasattr(o, "has_state") and o.has_state(volcado.state):
                if o.state_value_active(volcado):
                    return True
            if getattr(getattr(o, "definition", None), "id", None) == BOLSA_DEF and o.parent is None:
                if lote is not None and lote.is_position_on_lot(o.position):
                    return True
    except Exception:
        _log(traceback.format_exc())
    return False


def _cobrar_multa():
    try:
        from protocolbuffers import Consts_pb2
        hogar = services.active_household()
        razon = getattr(Consts_pb2, "TELEMETRY_INTERACTION_COST", 0)
        hogar.funds.try_remove(MULTA, razon, services.get_active_sim())
    except Exception:
        _log(traceback.format_exc())

    _notificar("Multa del servicio de basuras", "El basurero ha encontrado el cubo volcado o basura tirada por el suelo. Te han puesto una multa de {} simoleones.".format(MULTA))


def _es_casa_propia():
    try:
        hogar = services.active_household()
        return hogar is not None and hogar.home_zone_id == services.current_zone_id()
    except Exception:
        _log(traceback.format_exc())
        return False


def _notificar_aviso():
    texto = "¡El camión de la basura pasa hoy a las 22:00! Revisa que el cubo de fuera esté de pie y que no haya basura por el suelo, o te pondrán una multa de 20 §."
    try:
        from ui.ui_dialog_notification import UiDialogNotification
        from sims4.localization import LocalizationHelperTuning
        from distributor.shared_messages import IconInfoData
        import sims4.resources
        clave = sims4.resources.get_resource_key(ICONO_AVISO, sims4.resources.Types.PNG)
        n = UiDialogNotification.TunableFactory().default((services.get_active_sim()),
          text=(lambda *a, **k: LocalizationHelperTuning.get_raw_text(texto)),
          title=(lambda *a, **k: LocalizationHelperTuning.get_raw_text("Servicio de basuras")),
          icon=(lambda *a, **k: IconInfoData(icon_resource=clave)))
        n.show_dialog()
    except Exception:
        _log(traceback.format_exc())
        _notificar("Servicio de basuras", texto)


def _llamar_basurero():
    try:
        from sims4.resources import Types
        tipo = services.get_instance_manager(Types.SITUATION).get(SITUACION_BASURERO)
        if tipo is None:
            _log("No encuentro la situacion del basurero (falta el .package?)")
            return False
        services.get_zone_situation_manager().create_situation(tipo, user_facing=False)
        return True
    except Exception:
        _log(traceback.format_exc())
        return False


def _reloj():
    ahora = services.time_service().sim_now
    dia = int(ahora.absolute_days())
    hora = ahora.hour()
    if not _es_casa_propia():
        return
    if hora == HORA_AVISO and _estado["dia_aviso"] != dia:
        _estado["dia_aviso"] = dia
        _notificar_aviso()
    if hora == HORA_VISITA and _estado["dia_visita"] != dia:
        _estado["dia_visita"] = dia
        if _situacion() is None:
            _llamar_basurero()


def _empujar_buscar_cubo(sim):
    try:
        from sims4.resources import Types
        from interactions.context import InteractionContext, QueueInsertStrategy
        from interactions.priority import Priority
        afd = services.get_instance_manager(Types.INTERACTION).get(INTERACCION_BUSCAR_CUBO)
        if afd is None:
            return
        ctx = InteractionContext(sim, (InteractionContext.SOURCE_SCRIPT), (Priority.High), insert_strategy=(QueueInsertStrategy.NEXT))
        r = sim.push_super_affordance(afd, None, ctx)
        _log("Empujado buscar cubo: {}".format(r))
    except Exception:
        _log(traceback.format_exc())


def _poner_mono(sim):
    """Pone el mono amarillo en la ropa que lleva ahora el basurero (sin casco, conserva los zapatos)."""
    try:
        cat, idx = sim.sim_info.get_current_outfit()
    except Exception:
        _log(traceback.format_exc())
        return
    _poner_mono_en(sim.sim_info, cat, idx)


def _poner_mono_en(si, cat, idx):
    """Pone el mono amarillo en el conjunto (cat, idx) del sim."""
    try:
        from sims.outfits.outfit_enums import BodyType
        msg = si.save_outfits()
        n = -1
        cambiado = False
        for o in msg.outfits:
            if int(o.category) != int(cat):
                continue
            n += 1
            if n != idx:
                continue
            quitar = {int(BodyType.FULL_BODY), int(BodyType.UPPER_BODY), int(BodyType.LOWER_BODY), int(BodyType.HAT)}
            ids = list(o.parts.ids)
            tipos = list(o.body_types_list.body_types)
            nuevos = [(i, t) for i, t in zip(ids, tipos) if int(t) not in quitar]
            nuevos.append((MONO_AMARILLO, int(BodyType.FULL_BODY)))
            del o.parts.ids[:]
            o.parts.ids.extend([i for i, t in nuevos])
            del o.body_types_list.body_types[:]
            o.body_types_list.body_types.extend([t for i, t in nuevos])
            cambiado = True
            break
        if cambiado:
            si._base.outfits = msg.SerializeToString()
            si.resend_outfits()
            try:
                si.resend_current_outfit()
            except Exception:
                pass
            _log("Mono amarillo puesto")
        else:
            _log("No encontre la ropa actual del basurero ({}, {})".format(cat, idx))
    except Exception:
        _log(traceback.format_exc())


def _al_entrar_en_situacion(situacion, sim):
    """Pone el mono en la ropa de la situacion en cuanto el basurero entra, para que llegue ya con el."""
    if getattr(situacion, "guid64", 0) != SITUACION_BASURERO:
        return
    try:
        from sims.outfits.outfit_enums import OutfitCategory
        si = sim.sim_info
        ropa = (OutfitCategory.SITUATION, 0)
        if not si.has_outfit(ropa):
            ropa = si.get_current_outfit()
        _poner_mono_en(si, ropa[0], ropa[1])
        if si.get_current_outfit() != ropa:
            si.set_current_outfit(ropa)
        _log("Mono puesto al llegar el basurero")
    except Exception:
        _log(traceback.format_exc())


def _haciendo(sim, guid):
    try:
        for si in list(sim.si_state):
            if getattr(getattr(si, "affordance", None), "guid64", 0) == guid:
                return True
    except Exception:
        _log(traceback.format_exc())
    return False


def _es_basurero(sim):
    sit = _situacion()
    return sit is not None and any(s is sim for s in sit.all_sims_in_situation_gen())


def _es_de_mi_casa(sim):
    try:
        hogar = services.active_household()
        return hogar is not None and sim.household_id == hogar.id
    except Exception:
        return False


def _subir_amistad(sim, otro, cantidad):
    try:
        services.relationship_service().add_relationship_score(sim.sim_id, otro.sim_id, cantidad)
    except Exception:
        _log(traceback.format_exc())


def _notificar_consejo():
    import random
    texto = random.choice(CONSEJOS_RECICLAJE)
    try:
        from ui.ui_dialog_notification import UiDialogNotification
        from sims4.localization import LocalizationHelperTuning
        from distributor.shared_messages import IconInfoData
        import sims4.resources
        clave = sims4.resources.get_resource_key(ICONO_RECICLAJE, sims4.resources.Types.PNG)
        n = UiDialogNotification.TunableFactory().default((services.get_active_sim()),
          text=(lambda *a, **k: LocalizationHelperTuning.get_raw_text(texto)),
          title=(lambda *a, **k: LocalizationHelperTuning.get_raw_text("El basurero dice:")),
          icon=(lambda *a, **k: IconInfoData(icon_resource=clave)))
        n.show_dialog()
    except Exception:
        _log(traceback.format_exc())
        _notificar("El basurero dice:", texto)


def _saludar(sim, basurero):
    _subir_amistad(sim, basurero, AMISTAD_SALUDAR)
    try:
        from sims4.resources import Types
        buff = services.get_instance_manager(Types.BUFF).get(BUFF_BASURERO_SIMPATICO)
        if buff is None:
            _log("No encuentro el estado de animo del basurero (falta el .package?)")
        else:
            sim.sim_info.add_buff_from_op(buff)
    except Exception:
        _log(traceback.format_exc())


def _preguntar_reciclaje(sim, basurero):
    _subir_amistad(sim, basurero, AMISTAD_RECICLAJE)
    _notificar_consejo()


def _anadir_interacciones_al_sim():
    """Mete las interacciones del basurero en el menu de los sims (una sola vez)."""
    from sims4.resources import Types
    sim_tuning = services.get_instance_manager(Types.OBJECT).get(OBJETO_SIM)
    interacciones = services.get_instance_manager(Types.INTERACTION)
    nuevas = []
    for guid in (INTERACCION_SALUDAR, INTERACCION_RECICLAJE):
        afd = interacciones.get(guid)
        if afd is None:
            _log("No encuentro la interaccion {} (falta el .package?)".format(guid))
        elif afd not in sim_tuning._super_affordances:
            nuevas.append(afd)
    if nuevas:
        sim_tuning._super_affordances = tuple(sim_tuning._super_affordances) + tuple(nuevas)


def _bolsas():
    return [o for o in list(services.object_manager().get_all())
            if getattr(getattr(o, "definition", None), "id", None) == BOLSA_DEF]


def _la_lleva(sim, o):
    p = getattr(o, "parent", None)
    vueltas = 0
    while p is not None and vueltas < 5:
        if p is sim:
            return True
        p = getattr(p, "parent", None)
        vueltas += 1
    return False


def _bolsa_de(sim):
    for o in _bolsas():
        if _la_lleva(sim, o):
            return o


def _bolsas_del_basurero():
    """Bolsas que no estaban en el solar cuando llego el basurero: las ha sacado el del cubo."""
    return [o for o in _bolsas() if o.id not in _estado["bolsas_previas"]]


def _quitar_bolsas(sims, tambien_en_la_mano):
    for o in _bolsas_del_basurero():
        if tambien_en_la_mano or not any(_la_lleva(sim, o) for sim in sims):
            try:
                o.destroy(source=o, cause="Jennikita: el basurero se lleva la basura")
            except Exception:
                _log(traceback.format_exc())


def _bolsa_tirada(sims):
    for o in _bolsas_del_basurero():
        if not any(_la_lleva(sim, o) for sim in sims):
            return True
    return False


def _terminar(sim, sit):
    """Cobra la multa si toca y manda irse al basurero con la bolsa en la mano."""
    _estado["entregado"] = True
    # Las bolsas que haya dejado en el suelo se quitan; la de la mano se la lleva
    _quitar_bolsas([sim], False)
    if _estado["camion"] is not None:
        _sonido(_estado["camion"], SONIDO_TRABAJANDO)
    if _estado["multa_pendiente"]:
        _estado["multa_pendiente"] = False
        _cobrar_multa()
    try:
        services.get_zone_situation_manager().make_sim_leave_now_must_run(sim)
        _estado["retirar"] = [sim, sit, MINUTOS_PARA_IRSE]
        _log("El basurero se va andando")
        return
    except Exception:
        _log(traceback.format_exc())
    try:
        sim.fade_out()
    except Exception:
        pass
    _estado["retirar"] = [sim, sit, 3]


def _tick(_=None):
    try:
        _reloj()
    except Exception:
        _log(traceback.format_exc())
    try:
        r = _estado["retirar"]
        if r is not None:
            r[2] -= 1
            if r[2] <= 0:
                _estado["retirar"] = None
                sim, sit = r[0], r[1]
                _quitar_bolsas([], True)
                if services.object_manager().get(sim.id) is not None:
                    try:
                        sim.schedule_destroy_asap(source=sim, cause="Jennikita: el basurero se sube al camion")
                    except Exception:
                        _log(traceback.format_exc())
                try:
                    services.get_zone_situation_manager().destroy_situation_by_id(sit.id)
                except Exception:
                    _log(traceback.format_exc())
                _log("Basurero subido al camion y visita terminada")
    except Exception:
        _log(traceback.format_exc())
    try:
        sit = _situacion()
        if sit is not None:
            _estado["fin"] = None
            if _estado["camion"] is None:
                _estado["camion"] = _crear_camion()
                _estado["entregado"] = False
                _estado["empujados"] = set()
                _estado["mono"] = {}
                _estado["con_bolsa"] = {}
                _estado["minutos"] = 0
                _estado["bolsas_previas"] = set(o.id for o in _bolsas())
                _estado["multa_pendiente"] = _hay_problemas()
                if _estado["camion"] is not None:
                    _sonido(_estado["camion"], SONIDO_LLEGADA)
            for sim in list(sit.all_sims_in_situation_gen()):
                if sim.id not in _estado["empujados"]:
                    _estado["empujados"].add(sim.id)
                    _empujar_buscar_cubo(sim)
                # Se pone varias veces por si el juego le cambia la ropa al llegar
                t = _estado["mono"].get(sim.id, 0) + 1
                _estado["mono"][sim.id] = t
                if t in (1, 3, 8, 20):
                    _poner_mono(sim)
            if _estado["entregado"]:
                _quitar_bolsas(list(sit.all_sims_in_situation_gen()), False)
            else:
                _estado["minutos"] += 1
                sims = list(sit.all_sims_in_situation_gen())
                for sim in sims:
                    motivo = None
                    if _bolsa_de(sim) is not None:
                        _estado["con_bolsa"][sim.id] = _estado["con_bolsa"].get(sim.id, 0) + 1
                        cogiendo = _haciendo(sim, INTERACCION_COGER_BOLSA)
                        if not cogiendo or _estado["con_bolsa"][sim.id] >= MINUTOS_MAX_COGIENDO_BOLSA:
                            motivo = "Ha cogido la basura del cubo"
                    elif _bolsa_tirada(sims):
                        motivo = "Ha soltado la bolsa en el suelo"
                    if motivo is None and _estado["minutos"] >= MINUTOS_MAX_VISITA:
                        motivo = "Lleva {} minutos en el solar sin terminar".format(_estado["minutos"])
                    if motivo is not None:
                        _log(motivo + ": se va")
                        _terminar(sim, sit)
                        break
        elif _estado["camion"] is not None:
            _quitar_bolsas([], False)
            # El basurero se ha ido: se quita el camion al rato
            if _estado["fin"] is None:
                _estado["fin"] = 0
            _estado["fin"] += 1
            if _estado["fin"] >= MINUTOS_CAMION_TRAS_IRSE:
                if _estado["multa_pendiente"]:
                    _estado["multa_pendiente"] = False
                    _cobrar_multa()
                _borrar_camiones()
                _estado["fin"] = None
    except Exception:
        _log(traceback.format_exc())


class _Dueno:
    pass


_DUENO = _Dueno()

def _arrancar():
    try:
        if _estado["alarma"] is not None:
            alarms.cancel_alarm(_estado["alarma"])
    except Exception:
        pass

    _estado.update(retirar=None, mono={}, empujados=set(), camion=None, multa_pendiente=False, entregado=False, fin=None,
                   bolsas_previas=set(), con_bolsa={}, minutos=0)
    if _situacion() is None:
        _borrar_camiones()
    try:
        _anadir_interacciones_al_sim()
    except Exception:
        _log(traceback.format_exc())
    _estado["alarma"] = alarms.add_alarm(_DUENO, date_and_time.create_time_span(minutes=1), _tick, repeating=True)


def _inyectar(clase, nombre):
    original = getattr(clase, nombre)

    @functools.wraps(original)
    def envoltura(*args, **kwargs):
        resultado = original(*args, **kwargs)
        try:
            _arrancar()
        except Exception:
            _log(traceback.format_exc())

        return resultado

    setattr(clase, nombre, envoltura)


try:
    import zone
    _inyectar(zone.Zone, "on_loading_screen_animation_finished")
except Exception:
    _log(traceback.format_exc())


# Clases de las interacciones con el basurero. El .package las usa con m="jennikita_basura".
try:
    from interactions.base.immediate_interaction import ImmediateSuperInteraction
    from event_testing.results import TestResult
except Exception:
    ImmediateSuperInteraction = None
    _log(traceback.format_exc())

if ImmediateSuperInteraction is not None:
    class _InteraccionBasurero(ImmediateSuperInteraction):
        _accion = None

        @classmethod
        def _test(cls, target, context, **kwargs):
            if target is None or not _es_basurero(target):
                return TestResult(False, "No es el basurero")
            if context.sim is None or context.sim is target or not _es_de_mi_casa(context.sim):
                return TestResult(False, "Solo para los sims de tu casa")
            return super()._test(target, context, **kwargs)

        def _run_interaction_gen(self, timeline):
            try:
                type(self)._accion(self.sim, self.target)
            except Exception:
                _log(traceback.format_exc())
            return True
            yield

    class SaludarBasurero(_InteraccionBasurero):
        _accion = staticmethod(_saludar)

    class PreguntarReciclaje(_InteraccionBasurero):
        _accion = staticmethod(_preguntar_reciclaje)


def _inyectar_entrada_situacion():
    from situations.custom_states.custom_states_situation import CustomStatesSituation
    for clase in CustomStatesSituation.__mro__:
        if "_on_add_sim_to_situation" in clase.__dict__:
            original = clase.__dict__["_on_add_sim_to_situation"]

            @functools.wraps(original)
            def envoltura(self, sim, *args, **kwargs):
                resultado = original(self, sim, *args, **kwargs)
                _al_entrar_en_situacion(self, sim)
                return resultado

            setattr(clase, "_on_add_sim_to_situation", envoltura)
            return
    _log("No encuentro _on_add_sim_to_situation: el mono se pondra al primer minuto")


try:
    _inyectar_entrada_situacion()
except Exception:
    _log(traceback.format_exc())

@sims4.commands.Command("jennikita.basurero", command_type=(sims4.commands.CommandType.Live))
def _cmd_basurero(_connection=None):
    """Truco de prueba: hace venir al basurero ahora mismo."""
    out = sims4.commands.CheatOutput(_connection)
    out("Basurero en camino." if _llamar_basurero() else "No se pudo llamar al basurero (mira Jennikita_Basura_log.txt).")


@sims4.commands.Command("jennikita.camion", command_type=(sims4.commands.CommandType.Live))
def _cmd_camion(_connection=None):
    """Truco de prueba: pone/quita el camion para ver donde queda."""
    out = sims4.commands.CheatOutput(_connection)
    if _estado["camion"] is None:
        _estado["camion"] = _crear_camion()
        out("Camion puesto." if _estado["camion"] else "No se pudo poner el camion.")
        if _estado["camion"] is not None:
            _sonido(_estado["camion"], SONIDO_LLEGADA)
    else:
        _borrar_camiones()
        out("Camion quitado.")


@sims4.commands.Command("jennikita.estado", command_type=(sims4.commands.CommandType.Live))
def _cmd_estado(_connection=None):
    """Diagnostico: dice que partes del mod encuentra el juego."""
    out = sims4.commands.CheatOutput(_connection)
    from sims4.resources import Types
    out("Script del camion de la basura: CARGADO")
    out("Situacion del basurero: " + ("OK" if services.get_instance_manager(Types.SITUATION).get(SITUACION_BASURERO) else "NO ENCONTRADA (falta Jennikita_CamionBasura.package)"))
    try:
        ok = services.definition_manager().get(CAMION_DEF) is not None
    except Exception:
        ok = False

    out("Camion (package del camion): " + ("OK" if ok else "NO ENCONTRADO"))
    out("Reloj activo: " + ("SI" if _estado["alarma"] is not None else "NO"))
    out("Es tu casa: " + ("SI" if _es_casa_propia() else "NO"))
    ahora = services.time_service().sim_now
    out("Hora del juego: {}:{:02d}".format(ahora.hour(), ahora.minute()))


_log("Script cargado")

def _ajustar(nombre, valor, _connection):
    out = sims4.commands.CheatOutput(_connection)
    try:
        _AJUSTE[nombre] = float(valor)
    except Exception:
        out("Pon un numero, por ejemplo 6.5")
        return
    _borrar_camiones()
    _estado["camion"] = _crear_camion()
    out("Ajuste actual -> calle: {calle}  largo: {largo}  giro: {giro}".format(**_AJUSTE))


@sims4.commands.Command("jennikita.camion_calle", command_type=(sims4.commands.CommandType.Live))
def _cmd_calle(valor='5.5', _connection=None):
    """Mueve el camion hacia la carretera (mas numero = mas hacia la carretera)."""
    _ajustar("calle", valor, _connection)


@sims4.commands.Command("jennikita.camion_largo", command_type=(sims4.commands.CommandType.Live))
def _cmd_largo(valor='8', _connection=None):
    """Mueve el camion a lo largo de la calle (negativo = hacia el otro lado)."""
    _ajustar("largo", valor, _connection)


@sims4.commands.Command("jennikita.camion_giro", command_type=(sims4.commands.CommandType.Live))
def _cmd_giro(valor='0', _connection=None):
    """Gira el camion (180 = darle la vuelta)."""
    _ajustar("giro", valor, _connection)


@sims4.commands.Command("jennikita.arreglar_sims", command_type=(sims4.commands.CommandType.Live))
def _cmd_arreglar(_connection=None):
    """Quita el mono del basurero a cualquier sim que lo lleve puesto por error (le genera ropa nueva)."""
    out = sims4.commands.CheatOutput(_connection)
    from sims.outfits.outfit_enums import OutfitCategory
    arreglados = 0
    for si in list(services.sim_info_manager().get_all()):
        try:
            msg = si.save_outfits()
            contador = {}
            para_arreglar = []
            for o in msg.outfits:
                cat = int(o.category)
                idx = contador.get(cat, 0)
                contador[cat] = idx + 1
                if any((x in MONOS_VIEJOS for x in list(o.parts.ids))):
                    para_arreglar.append((cat, idx))

            for (cat, idx) in para_arreglar:
                si.generate_outfit(OutfitCategory(cat), idx)

            if para_arreglar:
                si.resend_outfits()
                try:
                    si.resend_current_outfit()
                except Exception:
                    pass

                arreglados += 1
                _log("Ropa arreglada: {}".format(si.full_name))
        except Exception:
            _log(traceback.format_exc())

    out("Sims arreglados: {}".format(arreglados))


@sims4.commands.Command("jennikita.aviso", command_type=(sims4.commands.CommandType.Live))
def _cmd_aviso(_connection=None):
    """Truco de prueba: muestra ahora el aviso de las 21:00 (para ver el icono)."""
    _notificar_aviso()
    sims4.commands.CheatOutput(_connection)("Aviso mostrado.")

