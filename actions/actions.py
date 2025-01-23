# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
# from rasa_sdk import Action, Tracker
# from rasa_sdk.executor import CollectingDispatcher
#
#
# class ActionHelloWorld(Action):
#
#     def name(self) -> Text:
#         return "action_hello_world"
#
#     def run(self, dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
#         dispatcher.utter_message(text="Hello World!")
#
#         return []

import logging
import re
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.events import UserUtteranceReverted
from rasa_sdk.types import DomainDict
from fuzzywuzzy import process
import pandas as pd


# Carica il dataset
movies_df = pd.read_csv("Dataset/imdb_top_1000.csv")


actor_df = pd.concat([movies_df['Star1'], movies_df['Star2'], movies_df['Star3']]).unique()
director_df = movies_df['Director'].unique()
movies = movies_df['Series_Title'].unique()
valid_genre = ['Drama', 'Crime', 'Action', 'Adventure', 'Biography', 'History', 'Sci-Fi',
 'Romance', 'Western', 'Fantasy', 'Comedy', 'Thriller', 'Animation', 'Family',
 'War', 'Mystery', 'Music', 'Horror', 'Musical', 'Film-Noir', 'Sport']
soglia_fuzzy = 80

class ActionCountFilms(Action):
    def name(self) -> str:
        return "action_count_films"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict) -> list:
        form_author = tracker.get_slot("form_author")
        form_quality = tracker.get_slot("form_quality") or "none"

        # Verifica se il nome del regista è presente nel database
        all_directors = movies_df['Director'].unique()
        best_match, score = process.extractOne(form_author, all_directors, scorer=process.fuzz.partial_ratio)

        if score >= 80:  # Considera solo corrispondenze con un punteggio >= 80
            matched_author = best_match
        else:
            dispatcher.utter_message(
                text=f"😔 Sorry, no director matching '{form_author}' was found."
            )
            return [SlotSet("form_author", None), SlotSet("form_quality", None)]

        if form_quality == "none":
            # Filtra solo per il regista trovato
            filtered_movies = movies_df[movies_df['Director'] == matched_author]
            num_films = len(filtered_movies)
            if not filtered_movies.empty:
                dispatcher.utter_message(
                    text=f"🎬 The number of films by {matched_author} are {num_films}.\n"
                )
                for _, row in filtered_movies.iterrows():
                    dispatcher.utter_message(
                        text=f"🎞️ *Film: {row['Series_Title']}\n⭐ Rating: {row['IMDB_Rating']}",
                        image=row['Poster_Link']
                    )
            else:
                dispatcher.utter_message(
                    text=f"😔 Sorry, no films found for {matched_author}."
                )
        else:
            # Filtra per regista trovato e rating minimo
            form_quality = float(form_quality)
            filtered_movies = movies_df[
                (movies_df['Director'] == matched_author) &
                (movies_df['IMDB_Rating'] >= form_quality)
            ]
            num_films = len(filtered_movies)
            if not filtered_movies.empty:
                dispatcher.utter_message(
                    text=f"🎥 The number of films by {matched_author} with a rating higher than {form_quality} are {num_films}."
                )
                for _, row in filtered_movies.iterrows():
                    dispatcher.utter_message(
                        text=f"🎞️ Film: {row['Series_Title']}\n⭐ Rating: {row['IMDB_Rating']}",
                        image=row['Poster_Link']
                    )
            else:
                dispatcher.utter_message(
                    text=f"😔 Sorry, no films by {matched_author} with a rating higher than {form_quality} were found."
                )

        return [SlotSet("form_author", None),
                SlotSet("form_quality", None)]

        
class ActionResetDirectorForm(Action):
    def name(self) -> Text:
        return "action_reset_director_form"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        # Resetta gli slot a None
        return [SlotSet("form_author", None),
                SlotSet("form_quality", None)]
    
class ValidateFilmCountForm(FormValidationAction):
    def name(self) -> str:
        return "validate_film_count_form"

    async def validate_form_author(
    self, value: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
) -> dict:
        """
        Validates the 'form_author' slot to ensure it's a valid string (not empty) and contains no numbers.
        """
        # Verifica che il valore non contenga numeri
        logging.info(f"Dentro validate_form_author, form_author: {value}")
        if isinstance(value, str) and value.strip():
            if re.search(r"\d", value):  # Se contiene numeri
                dispatcher.utter_message(text="⚠️ The author's name should not contain numbers. Please try again.")
                logging.error(f"Invalid author input: {value}. It contains numbers.")
                return {"form_author": None}  # Reset the slot if it contains numbers
            else:
                logging.info(f"Valid author: {value}")
                return {"form_author": value}
        else:
            dispatcher.utter_message(text="⚠️ Please provide a valid author name.")
            logging.error(f"Invalid author input: {value}")
            return {"form_author": None}  # Reset the slot if invalid

    async def validate_form_quality(
        self, value: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> dict:
        """
        Validates the 'form_quality' slot to ensure it is a number between 0.0 and 10.0, or allows None.
        """
        logging.info(f"Validating form_quality: {value}")
        
        # Se il valore è "none" o None, salta la validazione
        if value == "none" or value is None:
            logging.info("Rating is optional, skipping validation.")
            return {"form_quality": value}

        # Normalizza il valore (sostituisci virgola con punto)
        logging.info(f"valore prima del replace {value}")
        value = value.replace(",", ".")
        logging.info(f"valore dopo il replace {value}")
        
        # Verifica che sia un numero valido tra 0.0 e 10.0
        try:
            rating = float(value)  # Prova a convertire in float
            if 0.0 <= rating <= 10.0:
                logging.info(f"Valid rating: {rating}")
                return {"form_quality": rating}
            else:
                dispatcher.utter_message(
                    text="⭐ The rating must be between 0 and 10. Please try again."
                )
                logging.warning(f"Rating out of range: {rating}")
        except ValueError:
            dispatcher.utter_message(
                text="⭐ Please provide a valid rating between 0 and 10 (e.g., 8 or 8.5)."
            )
            logging.error(f"Invalid rating input: {value}")

        return {"form_quality": None}  # Reset slot se invalido

class ActionProvideMovieRecommendation(Action):
    def name(self) -> Text:
        return "action_provide_movie_recommendation"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        # Ottieni i valori degli slot compilati
        min_release_year = tracker.get_slot("min_release_year")
        genre = tracker.get_slot("form_genre")  # Questo è ora una lista
        min_rating = tracker.get_slot("form_quality")

        # Controlla che tutti gli slot siano stati compilati
        if not (min_release_year and genre and min_rating):
            dispatcher.utter_message(text="⚠️ It seems like some information is missing. Please try again.")
            return []

        # Se 'genre' è una lista di generi, uniscili in un'unica stringa
        if isinstance(genre, list):
            genre = "|".join(genre)  # Uso del simbolo '|' per fare il match su uno o più generi

        # Filtra i film dal DataFrame basandosi sugli slot
        filtered_movies = self.filter_movies(min_release_year, genre, min_rating)

        # Se sono stati trovati film, invia i risultati
        if not filtered_movies.empty:
            dispatcher.utter_message(text="🎬 Here are some movies I recommend based on your preferences:")
            for _, row in filtered_movies.iterrows():
                dispatcher.utter_message(
                    text=(
                        f"📽️ Title: {row['Series_Title']} ({row['Released_Year']})\n"
                        f"⭐ Rating: {row['IMDB_Rating']}\n"
                        f"🎭 Genre: {row['Genre']}"
                    ),
                    image=row.get("Poster_Link", None),  # Invia immagine se disponibile
                )
        else:
            # Nessun film trovato
            dispatcher.utter_message(
                text="😔 Sorry, I couldn't find any movies matching your preferences. Try adjusting the criteria!"
            )

        # Resetta gli slot dopo la risposta
        return self.reset_slots()

    def filter_movies(self, min_release_year, genre, min_rating):
            """
            Filtra i film dal DataFrame basandosi sui criteri forniti.
            """
            movies_df["Released_Year"] = pd.to_numeric(movies_df["Released_Year"], errors="coerce").fillna(0).astype(int)
            filtered_movies = movies_df[
                (movies_df["Released_Year"] >= min_release_year if min_release_year else True)
                & (movies_df["Genre"].str.contains(genre, case=False, na=False) if genre else True)
                & (movies_df["IMDB_Rating"] >= min_rating if min_rating else True)
            ].head(5)
            return filtered_movies

    def reset_slots(self):
        """
        Resetta gli slot della form.
        """
        return [
            SlotSet("min_release_year", None),
            SlotSet("form_genre", None),
            SlotSet("form_quality", None),
        ]

class ActionResetMoviePreferences(Action):
    def name(self) -> Text:
        return "action_reset_movie_preferences"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        # Resetta gli slot a None
        return [
            SlotSet("min_release_year", None),
            SlotSet("form_genre", None),
            SlotSet("form_quality", None)
        ]

class ValidateMovieRecommendationForm(FormValidationAction):
    def name(self) -> str:
        return "validate_movie_recommendation_form"

    async def validate_min_release_year(
        self, value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return {"min_release_year": tracker.get_slot("min_release_year")}

    async def validate_form_genre(
    self, value: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
) -> dict:
        
        logging.info(f"Dentro validate_form_genre, form_genre: {value}")
        valid_genres = [g.lower() for g in valid_genre]
        
        # Se 'value' è già una lista, controlla ogni elemento
        if isinstance(value, list):
            genres = [genre.strip().lower() for genre in value]
        else:
            # Altrimenti, separa la stringa in base alla virgola
            genres = [genre.strip().lower() for genre in value.split(",")]

        logging.info(f"Input genre: {genres}")
        # Verifica che tutti i generi siano validi
        invalid_genres = [genre for genre in genres if genre not in valid_genres]

        if not invalid_genres:
            # Se tutti i generi sono validi, restituisci la lista
            return {"form_genre": genres}
        else:
            # Se ci sono generi non validi, invia un messaggio di errore
            dispatcher.utter_message(
                text=f"⚠️ The following genres are not valid: {', '.join(invalid_genres)}. Please choose from: {', '.join(valid_genres)}."
            )
            return {"form_genre": None}  # Resetta solo lo slot non valido

    async def validate_form_quality(
        self, value: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> dict:
        """
        Validates the 'form_quality' slot to ensure it is a number between 0.0 and 10.0, or allows None.
        """
        logging.info(f"Validating form_quality: {value}")
        
        # Se il valore è "none" o None, salta la validazione
        if value == "none" or value is None:
            logging.info("Rating is optional, skipping validation.")
            return {"form_quality": value}

        # Normalizza il valore (sostituisci virgola con punto)
        logging.info(f"valore prima del replace {value}")
        value = value.replace(",", ".")
        logging.info(f"valore dopo il replace {value}")
        
        # Verifica che sia un numero valido tra 0.0 e 10.0
        try:
            rating = float(value)  # Prova a convertire in float
            if 0.0 <= rating <= 10.0:
                logging.info(f"Valid rating: {rating}")
                return {"form_quality": rating}
            else:
                dispatcher.utter_message(
                    text="⭐ The rating must be between 0 and 10. Please try again."
                )
                logging.warning(f"Rating out of range: {rating}")
        except ValueError:
            dispatcher.utter_message(
                text="⭐ Please provide a valid rating between 0 and 10 (e.g., 8 or 8.5)."
            )
            logging.error(f"Invalid rating input: {value}")

        return {"form_quality": None}

class ValidateGrossVotesRecommendationForm(FormValidationAction):
    def name(self) -> str:
        return "validate_gross_votes_recommendation_form"

    async def validate_form_votes(
        self, value: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> dict:
        """
        Validates the 'form_votes' slot to ensure it's a positive integer.
        """
        # Verifica che il valore sia un numero intero positivo
        logging.info(f"Dentro validate_form_votes, form_votes = {value}")
        logging.info(f"Tipo di value form_votes: {type(value)}")
        value = str(value)
        if re.fullmatch(r"^\d+$", value):  # Valida che sia un numero intero
            try:
                votes = int(value)
                if votes > 0:
                    logging.info(f"Valid votes count: {votes}")
                    return {"form_votes": votes}
                else:
                    dispatcher.utter_message(text="⚠️ The number of votes must be a positive integer. Please try again.")
                    logging.error(f"Invalid votes input (not positive): {votes}")
            except ValueError:
                dispatcher.utter_message(text="⚠️ An unexpected error occurred. Please try again.")
                logging.error(f"Error parsing votes: {value}")
        else:
            dispatcher.utter_message(text="⚠️ Please provide a valid positive integer for the number of votes.")
            logging.error(f"Invalid votes input: {value}")

        return {"form_votes": None}  # Resetta lo slot se non è valido

    async def validate_form_gross(
        self, value: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> dict:
        """
        Validates the 'form_gross' slot to ensure it's a positive number (decimal or integer).
        """
        # Verifica che il valore sia un numero positivo, decimale o intero
        logging.info(f"Dentro validate_form_gross, form_gross = {value}")
        logging.info(f"Tipo di value form_gross: {type(value)}")
        value = str(value)
        if re.fullmatch(r"^\d+(\.\d+)?$", value):  # Valida che sia un numero positivo (intero o decimale)
            try:
                gross = float(value)
                if gross > 0:
                    logging.info(f"Valid gross earnings: {gross}")
                    return {"form_gross": gross}
                else:
                    dispatcher.utter_message(text="⚠️ The gross earnings must be a positive number. Please try again.")
                    logging.error(f"Invalid gross earnings (not positive): {gross}")
            except ValueError:
                dispatcher.utter_message(text="⚠️ An unexpected error occurred. Please try again.")
                logging.error(f"Error parsing gross earnings: {value}")
        else:
            dispatcher.utter_message(text="⚠️ Please provide a valid positive number for gross earnings.")
            logging.error(f"Invalid gross earnings input: {value}")

        return {"form_gross": None}  # Resetta lo slot se non è valido

class ActionGrossVotesRecommendation(Action):
    def name(self) -> Text:
        return "action_gross_votes_recommendation"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, 
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Estrazione dei valori dagli slot
        votes_threshold = tracker.get_slot("form_votes")
        gross_threshold = tracker.get_slot("form_gross")

        try:
            # Conversione esplicita in numeri
            votes_threshold = int(votes_threshold)
            gross_threshold = float(gross_threshold)
        except (ValueError, TypeError):
            dispatcher.utter_message(
                text="🚨 The values entered for votes or gross are invalid. Please use numbers (Decimal separator: '.')"
            )
            return []

        # Pulizia e conversione della colonna "Gross"
        movies_df["Gross"] = movies_df["Gross"].replace({',': ''}, regex=True)
        movies_df["Gross"] = pd.to_numeric(movies_df["Gross"], errors='coerce')

        # Filtraggio dei film
        filtered_movies = movies_df[
            (movies_df['No_of_Votes'] >= votes_threshold) & 
            (movies_df['Gross'] >= gross_threshold)
        ].dropna(subset=['Series_Title', 'No_of_Votes', 'Gross'])  # Rimuove righe con dati mancanti

        filtered_movies = filtered_movies.head(5)
        
        if not filtered_movies.empty:
            dispatcher.utter_message(text="🎥 Here are the top 5 films that match your criteria:")
            for _, movie in filtered_movies.iterrows():
                message = (
                    f"• {movie['Series_Title']}\n"
                    f"   - Votes: {movie['No_of_Votes']} (based on reviews)\n"
                    f"   - Gross: ${movie['Gross']}\n"
                )
                dispatcher.utter_message(text=message, image=movie['Poster_Link'])
            
        else:
            dispatcher.utter_message(
                text=f"😔 Sorry, I couldn't find any movies with at least {votes_threshold} votes and ${gross_threshold} gross."
            )

        # Resetta gli slot
        return [SlotSet("form_votes", None), SlotSet("form_gross", None)]


class ActionResetGrossVotesRecommendationForm(Action):
    def name(self) -> Text:
        return "action_reset_gross_votes_recommendation_form"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        # Resetta gli slot a None
        logging.info("SONO QUI")
        return [SlotSet("form_votes", None),
                SlotSet("form_gross", None)]
