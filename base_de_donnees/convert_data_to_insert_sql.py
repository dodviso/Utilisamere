"""
Ce script Python permet de générer des instructions SQL "INSERT INTO" à partir de fichiers de données de type :
CSV, JSON, GeoJSON, Excel.

Par défaut :
 - le nom du fichier est pris pour nommer la table
 - les noms des colonnes sont repris à l'identique
 - pas de schéma (sera placé donc dans le schéma "public")
 - des types de données par défaut vous seront suggérés

Dans l'interface, vous pouvez paramétrer tous ces éléments
"""

import os
import pandas as pd
import geopandas as gpd
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

def detect_data_type(dtype) -> str:
    """Détecter le type de données pour un dtype donné."""
    if pd.api.types.is_numeric_dtype(dtype):
        return 'NUMERIC'
    elif pd.api.types.is_string_dtype(dtype):
        return 'TEXT'
    elif pd.api.types.is_boolean_dtype(dtype):
        return 'BOOLEAN'
    else:
        return 'TEXT'

def generer_sql_create_table(schema: str, table_name: str, df: pd.DataFrame, column_mapping: dict, column_types: dict) -> str:
    """
    Fonction qui génère l'instruction SQL "CREATE TABLE" à partir des données du DataFrame.
    """
    columns = []
    # Filtrer les colonnes à inclure en fonction des paramètres
    included_columns = [col for col in df.columns if column_mapping.get(col) is not None]
    
    for col in included_columns:
        col_name = column_mapping.get(col, col)
        col_type = column_types.get(f'{col}_type', 'TEXT')  # Utiliser 'TEXT' par défaut si non spécifié
        columns.append(f"{col_name} {col_type}")

    column_definitions = ', '.join(columns)
    if schema:
        create_table_sql = f"CREATE TABLE {schema}.{table_name} ({column_definitions});"
    else:
        create_table_sql = f"CREATE TABLE {table_name} ({column_definitions});"

    return create_table_sql

def generer_sql_insert_into(schema: str, table_name: str, df: pd.DataFrame, column_mapping: dict) -> str:
    """ Génère les instructions SQL "INSERT INTO" pour les données du DataFrame avec les nouveaux noms de colonnes. """
    instructions_insert = []
    # Filtrer les colonnes à inclure en fonction des paramètres
    included_columns = [col for col in df.columns if column_mapping.get(col) is not None]
    for _, row in df[included_columns].iterrows():
        columns = ', '.join(column_mapping.get(col, col) for col in included_columns)
        values = ', '.join([
            f"'{str(value).replace("'", "''")}'" if isinstance(value, str) else ('NULL' if pd.isna(value) else str(value))
            for value in row
        ])
        if schema:
            insert_statement = f"INSERT INTO {schema}.{table_name} ({columns}) VALUES ({values});"
        else:
            insert_statement = f"INSERT INTO {table_name} ({columns}) VALUES ({values});"
        instructions_insert.append(insert_statement)
    return '\n'.join(instructions_insert)

class FileProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Générateur de SQL")

        self.files = []
        self.file_data = {}
        self.df_cache = {}
        self.param_window = None

        self.create_widgets()

    def create_widgets(self):
        # Sélectionner les fichiers
        self.select_files_button = tk.Button(self.root, text="Sélectionner les fichiers", command=self.select_files,
                                            relief="raised", borderwidth=2, padx=10, pady=5)
        self.select_files_button.pack(pady=10)
        self.apply_button_style(self.select_files_button)

        self.files_tree = ttk.Treeview(self.root, columns=("File", "Schema", "Table", "Actions"), show="headings")
        self.files_tree.heading("File", text="Fichier")
        self.files_tree.heading("Schema", text="Schéma")
        self.files_tree.heading("Table", text="Table")
        self.files_tree.heading("Actions", text="Paramétrer les colonnes")
        self.files_tree.pack(pady=10, fill=tk.BOTH, expand=True)

        self.files_tree.bind("<ButtonRelease-1>", self.on_item_click)

        # Bouton pour générer les fichiers SQL
        self.generate_button = tk.Button(self.root, text="Générer SQL", command=self.generate_sql_files,
                                         relief="raised", borderwidth=2, padx=10, pady=5)
        self.generate_button.pack(pady=10)
        self.apply_button_style(self.generate_button)

    def apply_button_style(self, button):
        button.config(bg="lightgrey", fg="black", font=("Helvetica", 10, "bold"))
        button.bind("<Enter>", self.on_hover)
        button.bind("<Leave>", self.on_leave)

    def on_hover(self, event):
        event.widget.config(bg="lightblue", cursor="hand")

    def on_leave(self, event):
        event.widget.config(bg="lightgrey", cursor="arrow")

    def select_files(self):
        filetypes = [("CSV files", "*.csv"), ("GeoJSON files", "*.geojson"), ("JSON files", "*.json"), ("Excel files", "*.xlsx")]
        self.files = filedialog.askopenfilenames(title="Sélectionner les fichiers", filetypes=filetypes)
        
        if not self.files:
            messagebox.showerror("Erreur", "Aucun fichier sélectionné.")
            return

        self.files_tree.delete(*self.files_tree.get_children())
        self.file_data.clear()
        self.df_cache.clear()

        for file in self.files:
            table_name = os.path.splitext(os.path.basename(file))[0]
            self.file_data[file] = {
                "schema": "",
                "table_name": table_name,
                "column_mapping": {},
                "column_types": {}
            }
            self.df_cache[file] = self.load_dataframe(file)  # Charger et mettre en cache le DataFrame
            self.files_tree.insert("", tk.END, values=(file, "", table_name, "Paramétrer"), iid=file)

    def on_item_click(self, event):
        item = self.files_tree.selection()
        if item:
            file_path = item[0]
            col_button = self.files_tree.identify_column(event.x)
            if col_button == "#4":  # La colonne "Actions"
                self.open_column_settings(file_path)

    def load_dataframe(self, file_path):
        """ Charger le DataFrame en fonction de l'extension du fichier. """
        if file_path.endswith('.csv'):
            return pd.read_csv(file_path, sep=';')
        elif file_path.endswith('.geojson'):
            gdf = gpd.read_file(file_path)
            df = gdf.to_crs(epsg=2154).rename(columns={'geometry': 'geom'})
            df['geom'] = df['geom'].apply(lambda geom: geom.wkt)
            return df
        elif file_path.endswith('.json'):
            with open(file_path, 'r') as f:
                data = json.load(f)
            return pd.json_normalize(data)
        elif file_path.endswith('.xlsx'):
            return pd.read_excel(file_path)
        else:
            raise ValueError("Format de fichier non supporté.")

    def open_column_settings(self, file_path):
        if self.param_window and self.param_window.winfo_exists():
            self.param_window.destroy()

        self.param_window = tk.Toplevel(self.root)
        self.param_window.title("Paramétrer les colonnes")

        df = self.df_cache[file_path]  # Récupérer le DataFrame mis en cache
        file_data = self.file_data[file_path]  # Données de configuration du fichier

        # Frame pour les paramètres de la table
        param_frame = tk.Frame(self.param_window)
        param_frame.pack(pady=10, fill=tk.X)

        tk.Label(param_frame, text="Schéma:").pack(side=tk.LEFT, padx=5)
        self.schema_entry = tk.Entry(param_frame)
        self.schema_entry.insert(0, file_data["schema"])
        self.schema_entry.pack(side=tk.LEFT, padx=5)

        tk.Label(param_frame, text="Table:").pack(side=tk.LEFT, padx=5)
        self.table_entry = tk.Entry(param_frame)
        self.table_entry.insert(0, file_data["table_name"])
        self.table_entry.pack(side=tk.LEFT, padx=5)

        # Frame pour les colonnes
        self.file_frame = tk.Frame(self.param_window)
        self.file_frame.pack(pady=10, fill=tk.BOTH, expand=True)

        self.entries = []
        self.check_vars = []
        self.type_vars = []

        # Récupérer l'état des colonnes (inclusion) depuis les données sauvegardées
        column_inclusion = file_data.get("column_inclusion", {})

        for col in df.columns:
            frame = tk.Frame(self.file_frame)
            frame.pack(pady=5, fill=tk.X)

            tk.Label(frame, text=f"{col}:").pack(side=tk.LEFT, padx=5)

            col_name_entry = tk.Entry(frame)
            col_name_entry.insert(0, file_data["column_mapping"].get(col, col))
            col_name_entry.pack(side=tk.LEFT)

            # Permettre une saisie personnalisée pour le type de données
            type_var = tk.StringVar(value=file_data["column_types"].get(f'{col}_type', 'TEXT'))
            type_entry = tk.Entry(frame, textvariable=type_var)
            type_entry.pack(side=tk.LEFT)

            # Initialiser check_var avec l'état enregistré ou avec True par défaut
            check_var = tk.BooleanVar(value=column_inclusion.get(col, True))
            tk.Checkbutton(frame, text="Inclure", variable=check_var).pack(side=tk.LEFT)

            self.entries.append(col_name_entry)
            self.type_vars.append(type_var)
            self.check_vars.append(check_var)

        save_button = tk.Button(self.param_window, text="Sauvegarder", command=lambda: self.save_column_settings(file_path),
                  relief="raised", borderwidth=2, padx=10, pady=5)
        save_button.pack(pady=10)
        self.apply_button_style(save_button)

    def save_column_settings(self, file_path):
        """ Sauvegarder les paramètres des colonnes et fermer la fenêtre. """
        column_mapping = {}
        column_types = {}
        column_inclusion = {}

        for entry, check_var, type_var, col in zip(self.entries, self.check_vars, self.type_vars, self.df_cache[file_path].columns):
            if check_var.get():
                column_mapping[col] = entry.get()
                column_types[f'{col}_type'] = type_var.get()
                column_inclusion[col] = True
            else:
                if col in column_mapping:
                    del column_mapping[col]
                if f'{col}_type' in column_types:
                    del column_types[f'{col}_type']
                column_inclusion[col] = False

        self.file_data[file_path]["schema"] = self.schema_entry.get()
        self.file_data[file_path]["table_name"] = self.table_entry.get()
        self.file_data[file_path]["column_mapping"] = column_mapping
        self.file_data[file_path]["column_types"] = column_types
        self.file_data[file_path]["column_inclusion"] = column_inclusion  # Sauvegarder l'état des cases à cocher

        # Mise à jour de l'onglet principal
        item = self.files_tree.selection()[0]
        self.files_tree.item(item, values=(file_path, self.schema_entry.get(), self.table_entry.get(), "Paramétrer"))

        self.param_window.destroy()

    def generate_sql_files(self):
        output_dir = filedialog.askdirectory(title="Choisir le dossier d'enregistrement des fichiers SQL")
        if not output_dir:
            messagebox.showerror("Erreur", "Aucun dossier de sortie sélectionné.")
            return

        errors = []  # Liste pour accumuler les erreurs
        success_files = []  # Liste pour accumuler les fichiers traités avec succès

        for file_path in self.files:
            try:
                df = self.df_cache[file_path]
                data = self.file_data[file_path]

                schema = data.get("schema", "")
                table_name = data.get("table_name", "")

                # Définir les colonnes par défaut si aucune configuration n'est fournie
                if not data.get("column_mapping"):
                    column_mapping = {col: col for col in df.columns}
                    column_types = {f'{col}_type': detect_data_type(df[col].dtype) for col in df.columns}
                else:
                    column_mapping = data.get("column_mapping", {})
                    column_types = data.get("column_types", {})

                # Générer le script SQL
                sql_script = (
                    f"{generer_sql_create_table(schema, table_name, df, column_mapping, column_types)}\n\n"
                    f"{generer_sql_insert_into(schema, table_name, df, column_mapping)}"
                )
                
                output_file = os.path.join(output_dir, f"{table_name}.sql")
                with open(output_file, 'w') as f:
                    f.write(sql_script)

                success_files.append(output_file)  # Ajouter le fichier à la liste des succès

            except Exception as e:
                errors.append(f"Erreur avec le fichier {file_path}: {e}")  # Ajouter l'erreur à la liste des erreurs

        if success_files:
            success_message = "Fichiers SQL générés avec succès :\n" + "\n".join(success_files)
            messagebox.showinfo("Succès", success_message)

        if errors:
            error_message = "Des erreurs se sont produites lors de la génération des fichiers SQL :\n" + "\n".join(errors)
            messagebox.showerror("Erreurs", error_message)
        elif not errors and not success_files:
            messagebox.showinfo("Information", "Aucun fichier généré.")



if __name__ == "__main__":
    root = tk.Tk()
    app = FileProcessorApp(root)
    root.mainloop()
