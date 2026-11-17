"""Texto original, auditoría y listas de revisión Buy to Rent."""

from pathlib import Path
import os
import re

import pandas as pd

from src import indicadores as ind


PATRON_VENTA = re.compile(
    r"\b(?:oficina|consultorio|hostel|hostal|local comercial|apto profesional|fondo de comercio|"
    r"a reciclar|a refaccionar|subasta|remate|usufructo|nuda propiedad|parte indivisa|en pozo|en construcci[oó]n|"
    r"anticipo|en blo(?:ck|que)|"
    r"cochera en venta|venta de cochera|venta de lote|venta de terreno)\b"
)
PATRON_TEMPORARIO = re.compile(
    r"\b(?:alquiler (?:temporario|temporal)|(?:alquila|alquiler|tarifa|precio|se alquila)"
    r"[^.;\n]{0,30}\bpor (?:d[ií]a|noche|semana|quincena)|estad[ií]a m[ií]nima|"
    r"m[ií]nimo (?:de )?\d+ noches|alquiler tur[ií]stico|corta estad[ií]a|"
    r"(?:modalidad|alquiler) (?:airbnb|booking))\b"
)
PATRON_TEMPORARIO_DEBIL = re.compile(
    r"\b(?:wifi incluido|incluye (?:wifi|servicios)|blanquer[ií]a|ropa de cama)\b"
)


def cargar_texto(raiz):
    ruta = Path(os.environ.get(
        "AVISOS_CRUDOS", raiz / "data/raw/mercadolibre_caba_scraping_completo.csv"
    ))
    if not ruta.is_file():
        raise FileNotFoundError(f"Descargar el CSV original en {ruta} o indicar AVISOS_CRUDOS.")
    texto = pd.read_csv(ruta, usecols=["Item_ID", "Titulo", "Descripcion"], dtype={"Item_ID": "string"})
    return texto.set_index("Item_ID", verify_integrity=True)


def senales_textuales(texto):
    """Devuelve coincidencias visibles. Las coincidencias requieren contexto."""
    unido = texto.Titulo.fillna("").str.cat(texto.Descripcion.fillna(""), sep="\n").str.lower()
    normalizado_venta = unido.str.replace(
        r"\b(?:cada oficina|oficina inmobiliaria independiente|profesional matriculado de la oficina)\b",
        "", regex=True
    )
    return pd.DataFrame({
        "Senal_Revision": normalizado_venta.str.findall(PATRON_VENTA).map(lambda a: ", ".join(dict.fromkeys(a))),
        "Importe_Es_Anticipo": unido.str.contains(
            r"\b(?:precio|importe) publicado (?:es|corresponde al?) (?:un |el )?(?:m[ií]nimo )?anticipo\b",
            regex=True
        ),
        "Temporario_Fuerte": unido.str.contains(PATRON_TEMPORARIO),
        "Temporario_Debil": unido.str.contains(PATRON_TEMPORARIO_DEBIL),
        "Tiene_Descripcion": texto.Descripcion.notna() & texto.Descripcion.str.strip().ne(""),
    })


def soporte_alquiler(ventas, alquileres, minimo=5):
    """Exige comparables de alquiler en el segmento y superficie en P1–P99 de la tipología."""
    conteos = alquileres.groupby(ind.CLAVES_SEGMENTO).size()
    claves = pd.MultiIndex.from_frame(ventas[ind.CLAVES_SEGMENTO])
    n = pd.Series(conteos.reindex(claves).to_numpy(), index=ventas.index).fillna(0)
    superficie = alquileres.groupby("Tipo_Propiedad").Superficie_Total_m2.quantile([.01, .99]).unstack()
    return n.ge(minimo) & ventas.Superficie_Total_m2.between(
        ventas.Tipo_Propiedad.map(superficie[.01]), ventas.Tipo_Propiedad.map(superficie[.99])
    )


def puntaje(avisos, rentabilidad=None):
    if rentabilidad is None:
        rentabilidad = avisos.Rentabilidad_Neta_Aviso
    return ind.indice_priorizacion(
        rentabilidad, avisos.Indice_Subvaluacion_Modelo,
        pd.Series(1.0, index=avisos.index), metodo="rango"
    )


def orden(scores, ids):
    return pd.DataFrame({"puntaje": scores, "id": ids}).dropna().sort_values(
        ["puntaje", "id"], ascending=[False, True]
    ).assign(puesto=lambda d: range(1, len(d) + 1)).puesto


def clasificar(avisos, texto, auditoria, presupuesto, *, usar_precio=False):
    salida = avisos.copy()
    ids = salida.Item_ID.astype("string")
    if ids.isna().any() or not ids.is_unique:
        raise ValueError("El ranking requiere un Item_ID único por aviso.")
    senales = senales_textuales(texto)
    salida = salida.join(senales, on=ids)
    decisiones = ids.map(auditoria.Decision)
    motivo = ids.map(auditoria.Motivo).fillna("")
    base = ind.ESCENARIOS_COSTOS["Base"]
    salida["Inversion_Inicial_USD"] = salida.Precio_USD * (1 + base.costos_entrada_pct)
    importe = salida.Precio_USD if usar_precio else salida.Inversion_Inicial_USD
    en_presupuesto = importe.between(*presupuesto)
    soporte = salida.En_Soporte_Alquiler.eq(1)
    comparable = soporte & salida.Rentabilidad_Neta_Aviso.notna() & salida.Indice_Subvaluacion_Modelo.notna()
    obra = salida.Estado_Inmueble_Limpio.fillna("").str.lower().isin(["en pozo", "en construcción"])
    anticipo = salida.Importe_Es_Anticipo.eq(True)
    elegible = comparable & en_presupuesto & ~obra & ~anticipo & decisiones.ne("Excluir").fillna(True)
    venta_con_alerta = (salida.Senal_Revision.fillna("").ne("") | ~salida.Tiene_Descripcion.eq(True))
    extremo = salida.Indice_Subvaluacion_Modelo.le(-.40) | salida.Flag_Precio_m2_Muy_Bajo.eq(1)

    observadas = salida.loc[salida.Flag_Expensas_Imputada.eq(0) & salida.Expensas_Validas_USD.notna()]
    claves = ["Barrio_Normalizado", "Tipo_Propiedad"]
    expensas = observadas.groupby(claves).Expensas_Validas_USD.agg(n="count", p75=lambda s: s.quantile(.75))
    p75 = expensas.p75.where(expensas.n.ge(5)).reindex(pd.MultiIndex.from_frame(salida[claves]))
    p75 = pd.Series(p75.to_numpy(), index=salida.index)
    imputada = salida.Flag_Expensas_Imputada.eq(1)
    conservadoras = salida.Expensas_Validas_USD.where(
        ~imputada, p75.clip(lower=salida.Expensas_Validas_USD)
    )
    salida["Rentabilidad_Neta_Expensas_P75"] = ind.rentabilidad_neta(
        salida.Alquiler_Estimado_USD, salida.Precio_USD, conservadoras, base
    )
    candidatos = salida.loc[elegible]
    score = puntaje(candidatos)
    orden_base = orden(score, ids)
    orden_p75 = orden(puntaje(candidatos, salida.loc[elegible, "Rentabilidad_Neta_Expensas_P75"]), ids)
    cae_por_expensas = imputada & (
        p75.isna() | (orden_base.reindex(salida.index).le(100) & ~orden_p75.reindex(salida.index).le(100))
    )
    revisar = (
        decisiones.eq("Validar").fillna(False)
        | ((venta_con_alerta | extremo) & decisiones.ne("Residencial").fillna(True))
        | cae_por_expensas
    )
    salida["Revision_Manual"] = decisiones.notna().astype(int)
    salida["Decision_Manual"] = decisiones.fillna("Pendiente")
    salida["Motivo_Revision"] = motivo
    salida["Alerta_Expensas"] = imputada
    salida["Alerta_Subvaluacion"] = extremo
    salida["Alerta_Texto"] = venta_con_alerta
    salida["Motivo_Exclusion"] = ""
    salida.loc[~comparable, "Motivo_Exclusion"] = "Fuera de soporte o indicador incompleto"
    salida.loc[comparable & ~en_presupuesto, "Motivo_Exclusion"] = "Fuera del presupuesto de inversión"
    salida.loc[obra, "Motivo_Exclusion"] = "Unidad sin entrega inmediata según el estado declarado"
    salida.loc[anticipo, "Motivo_Exclusion"] = "El precio publicado corresponde a un anticipo"
    exclusion_manual = decisiones.eq("Excluir").fillna(False)
    salida.loc[exclusion_manual, "Motivo_Exclusion"] = motivo[exclusion_manual]
    salida["Lista_Revision"] = "Excluidos"
    salida.loc[elegible & revisar, "Lista_Revision"] = "Validar antes"
    salida.loc[elegible & ~revisar, "Lista_Revision"] = "Principal"
    salida["En_Universo_Priorizacion"] = elegible.astype(int)
    salida["Orden_Antes_Alertas"] = orden_base
    salida["Orden_Expensas_P75"] = orden_p75
    salida["Indice_Priorizacion"] = score
    principal = salida.Lista_Revision.eq("Principal")
    salida["Orden_Revision"] = orden(score.loc[principal], ids)
    return salida
