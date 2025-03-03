from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'votre_clé_secrète'  # Nécessaire pour les messages flash

# Configuration MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Ayoub'
app.config['MYSQL_DB'] = 'formulaire'

mysql = MySQL(app)


# Fonction pour valider le format de l'email
def est_email_valide(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/formulaire', methods=['GET', 'POST'])
def formulaire():
    if request.method == 'POST':
        # Récupération des données du formulaire
        nom_complet = request.form.get('nom_complet', '').strip()
        ville = request.form.get('ville', '').strip()
        email = request.form.get('email', '').strip()

        # Validation des données
        erreurs = []
        if not nom_complet:
            erreurs.append('Le nom complet est obligatoire')
        if not ville:
            erreurs.append('La ville est obligatoire')
        if not email:
            erreurs.append("L'adresse email est obligatoire")
        elif not est_email_valide(email):
            erreurs.append("L'adresse email n'est pas valide")

        # S'il y a des erreurs, afficher le formulaire avec les erreurs
        if erreurs:
            for erreur in erreurs:
                flash(erreur, 'error')
            return render_template('formulaire.html',
                                   nom_complet=nom_complet,
                                   ville=ville,
                                   email=email)

        # Sinon, enregistrer les données dans MySQL
        try:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO inscriptions (nom_complet, ville, email) VALUES (%s, %s, %s)",
                        (nom_complet, ville, email))
            mysql.connection.commit()
            cur.close()

            flash("L'inscription a été enregistrée avec succès!", 'success')

            # Rediriger vers la page de confirmation
            return redirect(url_for('confirmation',
                                    nom_complet=nom_complet,
                                    ville=ville,
                                    email=email))
        except Exception as e:
            flash(f"Une erreur est survenue lors de l'enregistrement: {str(e)}", 'error')
            return render_template('formulaire.html',
                                   nom_complet=nom_complet,
                                   ville=ville,
                                   email=email)

    # Si c'est une requête GET, afficher le formulaire vide
    return render_template('formulaire.html')


@app.route('/confirmation')
def confirmation():
    nom_complet = request.args.get('nom_complet', '')
    ville = request.args.get('ville', '')
    email = request.args.get('email', '')

    return render_template('confirmation.html',
                           nom_complet=nom_complet,
                           ville=ville,
                           email=email)


@app.route('/inscrits')
def inscrits():
    # Paramètres de pagination et recherche
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    per_page = 10  # Nombre d'inscrits par page

    try:
        cur = mysql.connection.cursor()

        # Requête pour compter le nombre total d'inscrits (avec recherche si applicable)
        if search_query:
            count_query = """
                SELECT COUNT(*) FROM inscriptions 
                WHERE nom_complet LIKE %s OR ville LIKE %s OR email LIKE %s
            """
            search_param = f'%{search_query}%'
            cur.execute(count_query, (search_param, search_param, search_param))
        else:
            cur.execute("SELECT COUNT(*) FROM inscriptions")

        total_count = cur.fetchone()[0]
        total_pages = (total_count + per_page - 1) // per_page  # Arrondi au supérieur

        # Requête pour récupérer les inscrits de la page actuelle
        offset = (page - 1) * per_page

        if search_query:
            query = """
                SELECT id, nom_complet, ville, email, date_inscription 
                FROM inscriptions 
                WHERE nom_complet LIKE %s OR ville LIKE %s OR email LIKE %s
                ORDER BY id DESC
                LIMIT %s OFFSET %s
            """
            search_param = f'%{search_query}%'
            cur.execute(query, (search_param, search_param, search_param, per_page, offset))
        else:
            query = """
                SELECT id, nom_complet, ville, email, date_inscription 
                FROM inscriptions 
                ORDER BY id DESC
                LIMIT %s OFFSET %s
            """
            cur.execute(query, (per_page, offset))

        # Récupération des résultats
        columns = [col[0] for col in cur.description]
        inscrits = [dict(zip(columns, row)) for row in cur.fetchall()]

        # Conversion des objets datetime
        for inscrit in inscrits:
            if isinstance(inscrit['date_inscription'], bytes):
                inscrit['date_inscription'] = datetime.strptime(
                    inscrit['date_inscription'].decode('utf-8'),
                    '%Y-%m-%d %H:%M:%S'
                )

        cur.close()

        return render_template('inscrits.html',
                               inscrits=inscrits,
                               page=page,
                               total_pages=total_pages,
                               search_query=search_query)

    except Exception as e:
        flash(f"Une erreur est survenue lors de la récupération des inscrits: {str(e)}", 'error')
        return render_template('inscrits.html', inscrits=[], page=1, total_pages=0, search_query='')


@app.route('/inscrits/<int:id>')
def voir_inscrit(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM inscriptions WHERE id = %s", (id,))

        # Récupération du résultat
        columns = [col[0] for col in cur.description]
        row = cur.fetchone()

        if not row:
            flash("Cet inscrit n'existe pas.", 'error')
            return redirect(url_for('inscrits'))

        inscrit = dict(zip(columns, row))

        # Conversion de l'objet datetime
        if isinstance(inscrit['date_inscription'], bytes):
            inscrit['date_inscription'] = datetime.strptime(
                inscrit['date_inscription'].decode('utf-8'),
                '%Y-%m-%d %H:%M:%S'
            )

        cur.close()

        return render_template('voir_inscrit.html', inscrit=inscrit)

    except Exception as e:
        flash(f"Une erreur est survenue lors de la récupération des détails: {str(e)}", 'error')
        return redirect(url_for('inscrits'))


@app.route('/inscrits/supprimer/<int:id>')
def supprimer_inscrit(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM inscriptions WHERE id = %s", (id,))
        mysql.connection.commit()
        cur.close()

        flash("L'inscrit a été supprimé avec succès.", 'success')
    except Exception as e:
        flash(f"Une erreur est survenue lors de la suppression: {str(e)}", 'error')

    return redirect(url_for('inscrits'))


if __name__ == '__main__':
    app.run(debug=True)