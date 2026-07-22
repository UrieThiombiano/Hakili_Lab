from unittest.mock import MagicMock, patch

import requests.exceptions

from src.integrations import google_sheets as gs


def _patch_client(fake_rows_par_sheet_id: dict):
    def _open_by_key(sheet_id):
        ws = MagicMock()
        ws.get_all_records.return_value = fake_rows_par_sheet_id[sheet_id]
        sp = MagicMock()
        sp.sheet1 = ws
        return sp

    fake_client = MagicMock()
    fake_client.open_by_key.side_effect = _open_by_key
    return patch.object(gs, "_get_client", return_value=fake_client)


def test_fold_header_tolere_casse_accents_espaces_ponctuation():
    assert gs._fold_header("Reprend la classe?") == gs._fold_header("reprend_la_classe")
    assert gs._fold_header("Contact Parents") == gs._fold_header("  contact   parents  ")
    assert gs._fold_header("Centre") == gs._fold_header("CENTRE")


def test_contact_parents_ne_matche_jamais_whatsapp():
    """LE piège explicitement signalé par le chantier : la colonne
    "Contact Parents (Whatsapp)" ne doit JAMAIS être prise pour "Contact
    Parents", même après normalisation tolérante des en-têtes."""
    folded_attendu = gs._fold_header(gs._COLONNES_ELEVES["contact_parents"])
    folded_whatsapp = gs._fold_header("Contact Parents (Whatsapp)")
    assert folded_attendu != folded_whatsapp


def test_load_eleves_prend_contact_parents_pas_whatsapp():
    """Reproduit une ligne réelle où les deux colonnes contact diffèrent
    (cas observé dans le Sheet réel, ligne 19 : Contact Parents se termine
    par 68, Whatsapp par 62) — l'identifiant doit se construire sur 68."""
    gs.clear_cache()
    fake_rows = [
        {
            "Nom": "ADJIBADE", "Prenom": "Ayoka", "Classe": "3eme", "Centre": "Siao",
            "Ecole": "Ecole X", "Reprend la classe?": "Non", "Boursier": "NON",
            "Contact Parents": "75 54 64 68",
            "Contact Parents (Whatsapp)": "75 54 64 62",
        },
    ]
    with _patch_client({"FAKE_ELEVES_ID": fake_rows}), \
         patch.object(gs.settings, "google_sheet_eleves_id", "FAKE_ELEVES_ID"):
        eleves = gs.get_eleves()

    assert len(eleves) == 1
    assert eleves[0]["contact_parents"] == "75 54 64 68"
    assert "75546468" in eleves[0]["identifiant_hakili"]
    assert "75546462" not in eleves[0]["identifiant_hakili"]


def test_colonne_manquante_liste_les_en_tetes_trouves():
    gs.clear_cache()
    fake_rows = [{"Nom": "X", "Prenom": "Y"}]  # colonnes attendues manquantes
    with _patch_client({"FAKE_ELEVES_ID": fake_rows}), \
         patch.object(gs.settings, "google_sheet_eleves_id", "FAKE_ELEVES_ID"):
        try:
            gs.get_eleves()
            assert False, "aurait dû lever GoogleSheetsError"
        except gs.GoogleSheetsError as exc:
            message = str(exc)
            assert "manquante" in message.lower()
            assert "Nom" in message and "Y" not in message  # en-têtes trouvés bien listés
            assert "En-têtes trouvés" in message


def test_load_personnel_regroupe_par_nom_prenom_et_multi_classes():
    """Le Sheet a une ligne par affectation, pas par personne : une même
    personne peut apparaître plusieurs fois. Regroupement par (nom, prénom)
    — l'email est optionnel, ce n'est plus une clé d'identité fiable. Une
    cellule classe peut contenir plusieurs valeurs séparées par des
    virgules ("6eme, 5eme")."""
    gs.clear_cache()
    fake_rows = [
        {"Nom": "TRAORE", "Prenom": "Issa", "Role": "enseignant", "Centre": "Siao", "classe": "6eme, 5eme", "PIN": "1234", "Email": ""},
        {"Nom": "TRAORE", "Prenom": "Issa", "Role": "enseignant", "Centre": "Saaba", "classe": "Tle", "PIN": "", "Email": ""},
        {"Nom": "", "Prenom": "", "Role": "", "Centre": "Siao", "classe": "3eme", "PIN": "", "Email": ""},  # sans nom
    ]
    with _patch_client({"FAKE_PERSONNEL_ID": fake_rows}), \
         patch.object(gs.settings, "google_sheet_personnel_id", "FAKE_PERSONNEL_ID"):
        personnel = gs._load_personnel()

    assert len(personnel) == 1
    issa = personnel[0]
    assert issa["role"] == "enseignant"
    assert issa["pin"] == "1234"
    assert set(issa["affectations"]) == {("Siao", "6e"), ("Siao", "5e"), ("Saaba", "Tle")}


def test_load_personnel_role_vient_de_la_colonne_role():
    """Le rôle ne vient plus du fichier d'origine mais de la colonne "role"
    du Sheet — un administrateur peut donc être une simple ligne, sans
    classe et potentiellement sans centre."""
    gs.clear_cache()
    fake_rows = [
        {"Nom": "KABORE", "Prenom": "Mariam", "Role": "responsable", "Centre": "Saaba", "classe": "", "PIN": "5678", "Email": ""},
        {"Nom": "HAKILI", "Prenom": "Admin", "Role": "administrateur", "Centre": "", "classe": "", "PIN": "0000", "Email": ""},
    ]
    with _patch_client({"FAKE_PERSONNEL_ID": fake_rows}), \
         patch.object(gs.settings, "google_sheet_personnel_id", "FAKE_PERSONNEL_ID"):
        personnel = gs._load_personnel()

    par_nom = {p["nom"]: p for p in personnel}
    assert par_nom["KABORE"]["role"] == "responsable"
    assert par_nom["KABORE"]["affectations"] == [("Saaba", None)]
    assert par_nom["HAKILI"]["role"] == "administrateur"
    assert par_nom["HAKILI"]["pin"] == "0000"


def test_load_personnel_sans_pin_compte_mais_charge():
    """Une personne sans PIN ne pourra pas se connecter, mais elle doit
    quand même apparaître dans get_personnel() — jamais disparaître
    silencieusement faute de PIN (ou d'email, désormais optionnel)."""
    gs.clear_cache()
    fake_rows = [
        {"Nom": "SAWADOGO", "Prenom": "Boureima", "Role": "enseignant", "Centre": "Tampouy", "classe": "3eme", "PIN": "", "Email": ""},
    ]
    with _patch_client({"FAKE_PERSONNEL_ID": fake_rows}), \
         patch.object(gs.settings, "google_sheet_personnel_id", "FAKE_PERSONNEL_ID"):
        personnel = gs._load_personnel()

    assert len(personnel) == 1
    assert personnel[0]["pin"] == ""


def test_colonnes_optionnelles_absentes_du_sheet_ne_cassent_rien():
    """Un Sheet personnel sans colonne classe ni email (structurellement
    absentes, pas juste vides) ne doit jamais lever d'erreur — ce sont des
    colonnes optionnelles (voir _COLONNES_PERSONNEL_OPTIONNELLES)."""
    gs.clear_cache()
    fake_rows = [{"Nom": "KABORE", "Prenom": "Mariam", "Role": "responsable", "Centre": "Saaba", "PIN": "5678"}]
    with _patch_client({"FAKE_PERSONNEL_ID": fake_rows}), \
         patch.object(gs.settings, "google_sheet_personnel_id", "FAKE_PERSONNEL_ID"):
        personnel = gs._load_personnel()

    assert len(personnel) == 1
    assert personnel[0]["affectations"] == [("Saaba", None)]


def test_load_personnel_un_seul_sheet_enseignant_responsable_administrateur():
    """Le personnel (enseignant, responsable, administrateur) vit dans UN
    SEUL Sheet fusionné (GOOGLE_SHEET_PERSONNEL_ID) — les trois rôles
    doivent s'y charger correctement depuis le même identifiant de Sheet."""
    gs.clear_cache()
    fake_rows = [
        {"Nom": "TRAORE", "Prenom": "Issa", "Role": "enseignant", "Centre": "Siao", "classe": "6eme", "PIN": "1111", "Email": ""},
        {"Nom": "KABORE", "Prenom": "Mariam", "Role": "responsable", "Centre": "Saaba", "classe": "", "PIN": "2222", "Email": ""},
        {"Nom": "HAKILI", "Prenom": "Admin", "Role": "administrateur", "Centre": "", "classe": "", "PIN": "3333", "Email": ""},
    ]
    with _patch_client({"FAKE_PERSONNEL_ID": fake_rows}), \
         patch.object(gs.settings, "google_sheet_personnel_id", "FAKE_PERSONNEL_ID"):
        personnel = gs.get_personnel()

    assert len(personnel) == 3
    par_nom = {p["nom"]: p for p in personnel}
    assert par_nom["TRAORE"]["role"] == "enseignant"
    assert par_nom["KABORE"]["role"] == "responsable"
    assert par_nom["HAKILI"]["role"] == "administrateur"

    from src.services.auth_service import authentifier
    for nom, pin in (("TRAORE", "1111"), ("KABORE", "2222"), ("HAKILI", "3333")):
        resultat = authentifier(par_nom[nom], pin)
        assert resultat.status == "ok", f"{nom} n'a pas pu se connecter avec son PIN"
    assert authentifier(par_nom["HAKILI"], "0000").status == "pin_incorrect"


def test_centres_derives_convergent_anodins_et_signalent_les_rares():
    """"SIAO"/"Siao" doivent converger vers un seul centre (variation
    anodine de casse), sans alerte. Un centre vu une seule fois ("Tampuy")
    doit être signalé "suspect" — jamais bloqué, jamais corrigé."""
    from src.core.centre_normalizer import deriver_centres

    valeurs = ["SIAO", "Siao", "Siao", "Tampouy", "Tampouy", "Tampuy"]
    derives = deriver_centres(valeurs)

    from src.core.centre_normalizer import fold_centre
    assert derives[fold_centre("SIAO")]["count"] == 3
    assert derives[fold_centre("SIAO")]["suspect"] is False
    assert derives[fold_centre("Tampouy")]["suspect"] is False
    assert derives[fold_centre("Tampuy")]["count"] == 1
    assert derives[fold_centre("Tampuy")]["suspect"] is True
    # Tampuy et Tampouy restent deux centres DISTINCTS (jamais fusionnés).
    assert fold_centre("Tampuy") != fold_centre("Tampouy")


def test_double_role_detecte_generiquement_pas_par_nom():
    """TEST DE GÉNÉRICITÉ (chantier casquette) : une personne FICTIVE,
    différente de DIANE Abasse et GUIRA Hassami (les deux exemples réels du
    chantier), doit AUSSI obtenir "roles" à deux entrées si ses lignes
    correspondent à la RÈGLE GÉNÉRALE (role=responsable + au moins une
    affectation avec une classe enseignée) — preuve que la détection ne
    dépend d'aucun nom codé en dur. Personne à rôle unique non affectée."""
    gs.clear_cache()
    fake_rows = [
        # Personne fictive en double rôle : responsable SANS classe sur une
        # ligne, ET une affectation d'enseignement sur une autre ligne.
        {"Nom": "TESTFICTIF", "Prenom": "Alpha", "Role": "responsable", "Centre": "Siao", "classe": "", "PIN": "4444", "Email": ""},
        {"Nom": "TESTFICTIF", "Prenom": "Alpha", "Role": "responsable", "Centre": "Siao", "classe": "5eme", "PIN": "4444", "Email": ""},
        # Témoin à rôle unique : ne doit PAS être affecté par la détection.
        {"Nom": "TEMOIN", "Prenom": "Beta", "Role": "responsable", "Centre": "Siao", "classe": "", "PIN": "5555", "Email": ""},
    ]
    with _patch_client({"FAKE_PERSONNEL_ID": fake_rows}), \
         patch.object(gs.settings, "google_sheet_personnel_id", "FAKE_PERSONNEL_ID"):
        personnel = gs._load_personnel()

    par_nom = {p["nom"]: p for p in personnel}
    assert par_nom["TESTFICTIF"]["roles"] == ["enseignant", "responsable"]
    assert par_nom["TEMOIN"]["roles"] == ["responsable"]


def test_erreur_dns_classee_connectivite_pas_configuration():
    """Une coupure réseau (échec de résolution DNS, message caractéristique
    "Failed to resolve...") doit être classée GoogleSheetsConnectiviteError,
    jamais GoogleSheetsConfigError — la distinction pilote le message
    affiché (doux vs technique) et l'usage du cache de repli."""
    gs.clear_cache()
    gs._cache_repli.pop("eleves", None)
    gs._dernier_mode.pop("eleves", None)
    dns_exc = requests.exceptions.ConnectionError("Failed to resolve oauth2.googleapis.com")

    def _open_by_key(sheet_id):
        raise dns_exc

    fake_client = MagicMock()
    fake_client.open_by_key.side_effect = _open_by_key

    with patch.object(gs, "_get_client", return_value=fake_client), \
         patch.object(gs.settings, "google_sheet_eleves_id", "FAKE_ELEVES_ID"):
        try:
            gs.get_eleves()
            assert False, "aurait dû lever GoogleSheetsConnectiviteError"
        except gs.GoogleSheetsConnectiviteError:
            pass
        except gs.GoogleSheetsConfigError:
            assert False, "une coupure réseau ne doit jamais être classée configuration"


def test_cache_de_repli_sert_derniere_lecture_reussie_sur_coupure_reseau():
    """Après une lecture réussie, une coupure réseau doit servir la
    dernière lecture connue (cache de repli, sans expiration stricte) —
    jamais planter tant qu'une lecture a déjà réussi une fois."""
    gs.clear_cache()
    gs._cache_repli.pop("eleves", None)
    gs._dernier_mode.pop("eleves", None)

    good_rows = [{
        "Nom": "A", "Prenom": "B", "Classe": "3eme", "Centre": "Siao", "Ecole": "E",
        "Reprend la classe?": "Non", "Boursier": "Non",
        "Contact Parents": "70000001", "Contact Parents (Whatsapp)": "",
    }]

    def _open_by_key_ok(sheet_id):
        ws = MagicMock()
        ws.get_all_records.return_value = good_rows
        sp = MagicMock()
        sp.sheet1 = ws
        return sp

    client_ok = MagicMock()
    client_ok.open_by_key.side_effect = _open_by_key_ok
    with patch.object(gs, "_get_client", return_value=client_ok), \
         patch.object(gs.settings, "google_sheet_eleves_id", "FAKE_ELEVES_ID"):
        eleves = gs.get_eleves()
    assert len(eleves) == 1
    assert gs.get_statut_lecture("eleves")["mode"] == "frais"

    gs.clear_cache()  # simule le TTL court expiré, force une relecture

    def _open_by_key_ko(sheet_id):
        raise requests.exceptions.ConnectionError("Failed to resolve oauth2.googleapis.com")

    client_ko = MagicMock()
    client_ko.open_by_key.side_effect = _open_by_key_ko
    with patch.object(gs, "_get_client", return_value=client_ko), \
         patch.object(gs.settings, "google_sheet_eleves_id", "FAKE_ELEVES_ID"):
        eleves_repli = gs.get_eleves()

    assert len(eleves_repli) == 1
    assert gs.get_statut_lecture("eleves")["mode"] == "repli"


def test_erreur_configuration_ne_beneficie_jamais_du_repli():
    """Une colonne manquante (configuration) ne doit JAMAIS être masquée
    par le cache de repli, même si une lecture avait réussi juste avant —
    un vrai problème à corriger ne doit jamais être caché par d'anciennes
    données."""
    gs.clear_cache()
    gs._cache_repli.pop("eleves", None)
    gs._dernier_mode.pop("eleves", None)

    good_rows = [{
        "Nom": "A", "Prenom": "B", "Classe": "3eme", "Centre": "Siao", "Ecole": "E",
        "Reprend la classe?": "Non", "Boursier": "Non",
        "Contact Parents": "70000001", "Contact Parents (Whatsapp)": "",
    }]
    with _patch_client({"FAKE_ELEVES_ID": good_rows}), \
         patch.object(gs.settings, "google_sheet_eleves_id", "FAKE_ELEVES_ID"):
        gs.get_eleves()

    gs.clear_cache()
    bad_rows = [{"Prenom": "B"}]  # colonne "Nom" manquante -> configuration
    with _patch_client({"FAKE_ELEVES_ID": bad_rows}), \
         patch.object(gs.settings, "google_sheet_eleves_id", "FAKE_ELEVES_ID"):
        try:
            gs.get_eleves()
            assert False, "aurait dû lever GoogleSheetsConfigError, pas servir le repli"
        except gs.GoogleSheetsConfigError:
            pass
