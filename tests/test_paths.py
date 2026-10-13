"""Pruebas de la persistencia en disco."""

import json

from easyautoclicker.paths import json_path, list_json_names, load_json, save_json


def test_guardar_y_cargar(tmp_path):
    destino = tmp_path / "datos.json"
    save_json(str(destino), {"a": 1, "ñ": "acentos"})
    assert load_json(str(destino), None) == {"a": 1, "ñ": "acentos"}


def test_guardado_no_deja_archivos_temporales(tmp_path):
    destino = tmp_path / "datos.json"
    save_json(str(destino), {"a": 1})
    assert [p.name for p in tmp_path.iterdir()] == ["datos.json"]


def test_cargar_devuelve_el_default_si_falta_o_esta_roto(tmp_path):
    assert load_json(str(tmp_path / "no_existe.json"), {"x": 1}) == {"x": 1}
    roto = tmp_path / "roto.json"
    roto.write_text("{esto no es json", encoding="utf-8")
    assert load_json(str(roto), {"x": 2}) == {"x": 2}


def test_listado_ordenado_e_insensible_a_mayusculas(tmp_path):
    for nombre in ("Beta.json", "alfa.json", "otro.txt"):
        (tmp_path / nombre).write_text("{}", encoding="utf-8")
    assert list_json_names(str(tmp_path)) == ["alfa", "Beta"]


def test_listado_de_carpeta_inexistente(tmp_path):
    assert list_json_names(str(tmp_path / "nada")) == []


def test_json_path_limpia_caracteres_prohibidos(tmp_path):
    ruta = json_path(str(tmp_path), 'mi:macro?*')
    assert ruta is not None
    assert ruta.endswith("mimacro.json")
    assert json_path(str(tmp_path), "   ") is None
    assert json_path(str(tmp_path), None) is None


def test_el_json_queda_legible(tmp_path):
    destino = tmp_path / "datos.json"
    save_json(str(destino), {"clave": "año"})
    texto = destino.read_text(encoding="utf-8")
    assert "año" in texto
    assert json.loads(texto) == {"clave": "año"}
