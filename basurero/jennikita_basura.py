"""Camion de la basura (Jennikita) - script del mod.

A las 21:00 avisa de que pasa el camion; a las 22:00 llama al basurero. Cuando
el basurero llega al solar aparece el camion, el basurero vacia el cubo de
fuera y lleva la bolsa al camion. Si al llegar el cubo estaba volcado o habia
basura por el suelo, multa de 20 simoleones.

Este archivo es el codigo fuente. El juego carga la version compilada con
Python 3.7 que va dentro de Jennikita_CamionBasura.ts4script.
"""
import collections
import functools
import math
import os
import traceback

import alarms
import date_and_time
import services
import sims4.commands
import sims4.math
import sims4.resources

SITUACION_BASURERO = 0xB5CBB31D3CE72CFA
TRABAJO_BASURERO = 0xAF5BF760999B8199
CAMION_DEF = 0x9BD4033C82419786
BOLSA_DEF = 22174
SONIDO_LLEGADA = 4448119419397510525
SONIDO_TRABAJANDO = 544368327340296755
ESTADO_VOLCADO = 15354
MULTA = 20
INTERACCION_BUSCAR_CUBO = 0xA489B7117CD24A51
HORA_AVISO = 21
HORA_VISITA = 22

# Icono de la notificacion. En el .package es una imagen DDS (tipo 00B2D882),
# asi que la clave tiene que llevar ese tipo y no el de PNG.
ICONO_AVISO = 0xD4961EED372508C7
TIPO_IMAGEN_DDS = 0x00B2D882

DISTANCIA_A_LO_LARGO = 8.0
DISTANCIA_HACIA_CALLE = 5.5
GIRO_EXTRA_GRADOS = 0.0
DISTANCIA_ENTREGA = 7.0
MINUTOS_ESPERA_BASURERO = 30

# Nombre del archivo de registro que dejaban las versiones anteriores del mod.
LOG_ANTIGUO = "Jennikita_Basura_log.txt"

_AJUSTE = {
    "calle": DISTANCIA_HACIA_CALLE,
    "largo": DISTANCIA_A_LO_LARGO,
    "giro": GIRO_EXTRA_GRADOS,
}

_estado = {
    "empujados": set(),
    "tics_bolsa": 0,
    "tics_espera": 0,
    "esperando": None,
    "dia_aviso": -1,
    "dia_visita": -1,
    "camion": None,
    "multa_pendiente": False,
    "entregado": False,
    "fin": None,
    "alarma": None,
}

# Los mensajes se guardan en memoria (no se escribe ningun .txt).
# Se ven con el truco jennikita.estado.
_mensajes = collections.deque(maxlen=12)


def _log(msg):
    try:
        ahora = services.time_service().sim_now
        msg = "[{}:{:02d}] {}".format(ahora.hour(), ahora.minute(), msg)
    except Exception:
        pass
    _mensajes.append(str(msg))


def _log_error(donde):
    lineas = traceback.format_exc().strip().splitlines()
    _log("ERROR en {}: {}".format(donde, lineas[-1] if lineas else "?"))


def _borrar_log_antiguo():
    """Borra el Jennikita_Basura_log.txt que creaban las versiones anteriores."""
    try:
        ruta = os.path.abspath(__file__)
        while not ruta.lower().endswith(".ts4script"):
            nueva = os.path.dirname(ruta)
            if nueva == ruta:
                return
            ruta = nueva
        for carpeta in (os.path.dirname(ruta), os.path.expanduser("~")):
            archivo = os.path.join(carpeta, LOG_ANTIGUO)
            if os.path.isfile(archivo):
                os.remove(archivo)
    except Exception:
        pass


def _notificar(titulo, texto, icono=None):
    from ui.ui_dialog_notification import UiDialogNotification
    from sims4.localization import LocalizationHelperTuning
    n = UiDialogNotification.TunableFactory().default(
        services.get_active_sim(),
        text=lambda *a, **k: LocalizationHelperTuning.get_raw_text(texto),
        title=lambda *a, **k: LocalizationHelperTuning.get_raw_text(titulo))
    if icono is None:
        n.show_dialog()
    else:
        n.show_dialog(icon_override=icono)


def _icono_aviso():
    from distributor.shared_messages import IconInfoData
    clave = sims4.resources.get_resource_key(ICONO_AVISO, TIPO_IMAGEN_DDS)
    return IconInfoData(icon_resource=clave)


def _notificar_con_icono(titulo, texto):
    try:
        _notificar(titulo, texto, _icono_aviso())
        return
    except Exception:
        _log_error("notificacion con icono")
    try:
        _notificar(titulo, texto)
    except Exception:
        _log_error("notificacion")


def _sonido(obj, sonido):
    try:
        from audio.primitive import PlaySound
        PlaySound(obj, sonido).start()
    except Exception:
        _log_error("sonido")


def _situacion():
    sm = services.get_zone_situation_manager()
    if sm is None:
        return None
    for s in list(sm.running_situations()):
        if getattr(s, "guid64", 0) == SITUACION_BASURERO:
            return s
    return None


def _basureros(sit):
    """Sims de la situacion que ya estan de verdad en el mundo."""
    sims = []
    for sim in list(sit.all_sims_in_situation_gen()):
        if sim is not None and getattr(sim, "position", None) is not None:
            sims.append(sim)
    return sims


def _punto_llegada():
    zona = services.current_zone()
    sp = getattr(zona, "active_lot_arrival_spawn_point", None)
    if sp is None:
        return None, None
    return sp.get_approximate_center(), sp.routing_surface


def _crear_camion():
    centro, superficie = _punto_llegada()
    if centro is None:
        _log("Sin punto de llegada: no se pone el camion")
        return None
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
        _log("No se pudo crear el camion (falta el .package?)")
        return None
    camion.location = sims4.math.Location(
        sims4.math.Transform(sims4.math.Vector3(x, y, z), orientacion), superficie)
    return camion


def _borrar_camiones():
    om = services.object_manager()
    if om is not None:
        for o in list(om.get_all()):
            if getattr(getattr(o, "definition", None), "id", None) == CAMION_DEF:
                try:
                    o.destroy(source=o, cause="Jennikita: fin del camion de la basura")
                except Exception:
                    _log_error("borrar camion")
    _estado["camion"] = None


def _hay_problemas():
    """Cubo de fuera volcado o bolsas/montones de basura tirados por el suelo del solar."""
    try:
        from sims4.resources import Types
        volcado = services.get_instance_manager(Types.OBJECT_STATE).get(ESTADO_VOLCADO)
        lote = services.active_lot()
        for o in list(services.object_manager().get_all()):
            if (volcado is not None and hasattr(o, "has_state")
                    and o.has_state(volcado.state) and o.state_value_active(volcado)):
                return True
            if (getattr(getattr(o, "definition", None), "id", None) == BOLSA_DEF
                    and o.parent is None and lote is not None
                    and lote.is_position_on_lot(o.position)):
                return True
    except Exception:
        _log_error("revisar basura")
    return False


def _cobrar_multa():
    try:
        from protocolbuffers import Consts_pb2
        hogar = services.active_household()
        razon = getattr(Consts_pb2, "TELEMETRY_INTERACTION_COST", 0)
        hogar.funds.try_remove(MULTA, razon, services.get_active_sim())
    except Exception:
        _log_error("cobrar multa")
    _notificar_con_icono(
        "Multa del servicio de basuras",
        "El basurero ha encontrado el cubo volcado o basura tirada por el suelo. "
        "Te han puesto una multa de {} simoleones.".format(MULTA))


def _es_casa_propia():
    try:
        hogar = services.active_household()
        return hogar is not None and hogar.home_zone_id == services.current_zone_id()
    except Exception:
        _log_error("comprobar casa")
        return False


def _notificar_aviso():
    _notificar_con_icono(
        "Servicio de basuras",
        "¡El camión de la basura pasa hoy a las 22:00! Revisa que el cubo de fuera "
        "esté de pie y que no haya basura por el suelo, o te pondrán una multa de 20 §.")


def _crear_situacion(tipo, con_invitado=True):
    """Crea la situacion pidiendo que el basurero venga de fuera del solar.

    Sin lista de invitados el juego lo trata como un NPC de fondo: si hay
    muchos Sims en el solar no lo hace aparecer, o usa a alguien que ya esta
    por alli. Con MUST_SPAWN y prioridad de invitado importante, el basurero
    siempre llega desde el punto de llegada.
    """
    sm = services.get_zone_situation_manager()
    if not con_invitado:
        return bool(sm.create_situation(tipo, user_facing=False))
    try:
        from sims4.resources import Types
        from situations.situation_guest_list import SituationGuestList, SituationGuestInfo
        from situations.bouncer.bouncer_types import RequestSpawningOption, BouncerRequestPriority
        trabajo = services.get_instance_manager(Types.SITUATION_JOB).get(TRABAJO_BASURERO)
        if trabajo is not None:
            invitados = SituationGuestList(invite_only=True)
            invitados.add_guest_info(SituationGuestInfo(
                0, trabajo, RequestSpawningOption.MUST_SPAWN, BouncerRequestPriority.EVENT_VIP))
            if sm.create_situation(tipo, guest_list=invitados, user_facing=False):
                return "invitado"
            _log("El juego no creo la situacion con invitado; se intenta sin lista")
        else:
            _log("No encuentro el trabajo del basurero (falta el .package?)")
    except Exception:
        _log_error("crear situacion con invitado")
    return bool(sm.create_situation(tipo, user_facing=False))


def _llamar_basurero(con_invitado=True):
    try:
        from sims4.resources import Types
        tipo = services.get_instance_manager(Types.SITUATION).get(SITUACION_BASURERO)
        if tipo is None:
            _log("No encuentro la situacion del basurero (falta el .package?)")
            return False
        modo = _crear_situacion(tipo, con_invitado)
        if not modo:
            _log("El juego no quiso crear la situacion del basurero")
            return False
        _estado["tics_espera"] = 0
        _estado["esperando"] = "invitado" if modo == "invitado" else "normal"
        _log("Basurero llamado")
        return True
    except Exception:
        _log_error("llamar al basurero")
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
            _log("No encuentro la interaccion de buscar el cubo (falta el .package?)")
            return
        ctx = InteractionContext(sim, InteractionContext.SOURCE_SCRIPT, Priority.High,
                                 insert_strategy=QueueInsertStrategy.NEXT)
        if not sim.push_super_affordance(afd, None, ctx):
            _log("El basurero no pudo ir a buscar el cubo")
    except Exception:
        _log_error("mandar al basurero al cubo")


def _bolsa_de(sim):
    for o in list(services.object_manager().get_all()):
        if getattr(getattr(o, "definition", None), "id", None) != BOLSA_DEF:
            continue
        p = getattr(o, "parent", None)
        vueltas = 0
        while p is not None and vueltas < 5:
            if p is sim:
                return o
            p = getattr(p, "parent", None)
            vueltas += 1
    return None


def _dist(a, b):
    return math.sqrt((a.x - b.x) ** 2 + (a.z - b.z) ** 2)


def _trasera_camion():
    c = _estado["camion"]
    if c is None:
        return None
    try:
        adelante = c.orientation.transform_vector(sims4.math.Vector3.Z_AXIS())
        return sims4.math.Vector3(c.position.x - adelante.x * 6.5, c.position.y,
                                  c.position.z - adelante.z * 6.5)
    except Exception:
        return c.position


def _nueva_visita():
    _estado["entregado"] = False
    _estado["empujados"] = set()
    _estado["tics_bolsa"] = 0
    _estado["multa_pendiente"] = _hay_problemas()


def _basurero_no_llega(sit):
    """Plan B: si el basurero pedido como invitado no aparece, se vuelve a
    llamar de la forma normal (la de la version anterior del mod)."""
    modo = _estado["esperando"]
    _estado["esperando"] = None
    _estado["tics_espera"] = 0
    if sit is not None:
        try:
            services.get_zone_situation_manager().destroy_situation_by_id(sit.id)
        except Exception:
            _log_error("cancelar visita")
    if modo == "invitado":
        _log("El basurero no aparecia; se le vuelve a llamar de otra forma")
        _llamar_basurero(con_invitado=False)
    else:
        _log("El basurero no ha llegado a aparecer")


def _tick(_=None):
    try:
        _reloj()
    except Exception:
        _log_error("reloj")

    try:
        sit = _situacion()
        if sit is not None:
            _estado["fin"] = None
            sims = _basureros(sit)
            if not sims:
                # El camion llega con el basurero, no antes.
                if _estado["esperando"] is not None:
                    _estado["tics_espera"] += 1
                    if _estado["tics_espera"] >= MINUTOS_ESPERA_BASURERO:
                        _basurero_no_llega(sit)
                return
            _estado["esperando"] = None
            if _estado["camion"] is None:
                _estado["camion"] = _crear_camion()
                _nueva_visita()
                _log("Ha llegado el basurero")
                if _estado["camion"] is not None:
                    _sonido(_estado["camion"], SONIDO_LLEGADA)

            for sim in sims:
                if sim.id not in _estado["empujados"]:
                    _estado["empujados"].add(sim.id)
                    _empujar_buscar_cubo(sim)

            if not _estado["entregado"]:
                centro, _s = _punto_llegada()
                trasera = _trasera_camion()
                for sim in sims:
                    bolsa = _bolsa_de(sim)
                    if bolsa is None:
                        continue
                    d1 = _dist(sim.position, centro) if centro is not None else 999
                    d2 = _dist(sim.position, trasera) if trasera is not None else 999
                    _estado["tics_bolsa"] += 1
                    if min(d1, d2) <= DISTANCIA_ENTREGA:
                        _estado["entregado"] = True
                        try:
                            bolsa.destroy(source=sim, cause="Jennikita: bolsa al camion")
                        except Exception:
                            _log_error("entregar bolsa")
                        _log("Bolsa entregada en el camion")
                        if _estado["camion"] is not None:
                            _sonido(_estado["camion"], SONIDO_TRABAJANDO)
                        if _estado["multa_pendiente"]:
                            _estado["multa_pendiente"] = False
                            _cobrar_multa()
                        break
        elif _estado["esperando"] is not None:
            # La situacion se acabo sin que el basurero llegara a aparecer.
            _estado["tics_espera"] += 1
            if _estado["tics_espera"] >= 3:
                _basurero_no_llega(None)
        elif _estado["camion"] is not None:
            if _estado["fin"] is None:
                _estado["fin"] = 0
            _estado["fin"] += 1
            if _estado["fin"] >= 10:
                if _estado["multa_pendiente"]:
                    _estado["multa_pendiente"] = False
                    _cobrar_multa()
                _borrar_camiones()
                _estado["fin"] = None
                _log("El camion se ha ido")
    except Exception:
        _log_error("tick")


class _Dueno:
    pass


_DUENO = _Dueno()


def _arrancar():
    try:
        if _estado["alarma"] is not None:
            alarms.cancel_alarm(_estado["alarma"])
    except Exception:
        pass
    _estado.update(empujados=set(), tics_bolsa=0, tics_espera=0, esperando=None, camion=None,
                   multa_pendiente=False, entregado=False, fin=None)
    # El camion que se guardo con la partida se quita siempre; si el basurero
    # sigue en el solar, el siguiente tick lo vuelve a poner (sin duplicarlo).
    _borrar_camiones()
    _estado["alarma"] = alarms.add_alarm(
        _DUENO, date_and_time.create_time_span(minutes=1), _tick, repeating=True)


def _inyectar(clase, nombre):
    original = getattr(clase, nombre)

    @functools.wraps(original)
    def envoltura(*args, **kwargs):
        resultado = original(*args, **kwargs)
        try:
            _arrancar()
        except Exception:
            _log_error("arrancar")
        return resultado

    setattr(clase, nombre, envoltura)


_borrar_log_antiguo()

try:
    import zone
    _inyectar(zone.Zone, "on_loading_screen_animation_finished")
except Exception:
    _log_error("enganchar con la carga del solar")


@sims4.commands.Command("jennikita.basurero", command_type=sims4.commands.CommandType.Live)
def _cmd_basurero(_connection=None):
    """Truco de prueba: hace venir al basurero ahora mismo."""
    out = sims4.commands.CheatOutput(_connection)
    if _situacion() is not None:
        out("El basurero ya esta de camino o en el solar.")
    elif _llamar_basurero():
        out("Basurero en camino. El camion aparece cuando el llega.")
    else:
        out("No se pudo llamar al basurero (escribe jennikita.estado).")


@sims4.commands.Command("jennikita.camion", command_type=sims4.commands.CommandType.Live)
def _cmd_camion(_connection=None):
    """Truco de prueba: pone/quita solo el camion (sin basurero) para ver donde queda."""
    out = sims4.commands.CheatOutput(_connection)
    if _estado["camion"] is None:
        _estado["camion"] = _crear_camion()
        out("Camion puesto (solo el camion, sin basurero)." if _estado["camion"]
            else "No se pudo poner el camion.")
        if _estado["camion"] is not None:
            _sonido(_estado["camion"], SONIDO_LLEGADA)
    else:
        _borrar_camiones()
        out("Camion quitado.")


@sims4.commands.Command("jennikita.estado", command_type=sims4.commands.CommandType.Live)
def _cmd_estado(_connection=None):
    """Diagnostico: dice que partes del mod encuentra el juego y los ultimos mensajes."""
    out = sims4.commands.CheatOutput(_connection)
    from sims4.resources import Types
    out("Script del camion de la basura: CARGADO")
    out("Situacion del basurero: " + (
        "OK" if services.get_instance_manager(Types.SITUATION).get(SITUACION_BASURERO)
        else "NO ENCONTRADA (falta Jennikita_CamionBasura.package)"))
    try:
        ok = services.definition_manager().get(CAMION_DEF) is not None
    except Exception:
        ok = False
    out("Camion (package del camion): " + ("OK" if ok else "NO ENCONTRADO"))
    out("Reloj activo: " + ("SI" if _estado["alarma"] is not None else "NO"))
    out("Es tu casa: " + ("SI" if _es_casa_propia() else "NO"))
    sit = _situacion()
    if sit is None:
        out("Basurero: no hay visita ahora")
    else:
        sims = _basureros(sit)
        out("Basurero: " + ("en el solar" if sims else "de camino (aun no ha aparecido)"))
    ahora = services.time_service().sim_now
    out("Hora del juego: {}:{:02d}".format(ahora.hour(), ahora.minute()))
    if _mensajes:
        out("Ultimos mensajes:")
        for m in list(_mensajes):
            out("  " + m)


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


@sims4.commands.Command("jennikita.camion_calle", command_type=sims4.commands.CommandType.Live)
def _cmd_calle(valor="5.5", _connection=None):
    """Mueve el camion hacia la carretera (mas numero = mas hacia la carretera)."""
    _ajustar("calle", valor, _connection)


@sims4.commands.Command("jennikita.camion_largo", command_type=sims4.commands.CommandType.Live)
def _cmd_largo(valor="8", _connection=None):
    """Mueve el camion a lo largo de la calle (negativo = hacia el otro lado)."""
    _ajustar("largo", valor, _connection)


@sims4.commands.Command("jennikita.camion_giro", command_type=sims4.commands.CommandType.Live)
def _cmd_giro(valor="0", _connection=None):
    """Gira el camion (180 = darle la vuelta)."""
    _ajustar("giro", valor, _connection)


_log("Script cargado")
