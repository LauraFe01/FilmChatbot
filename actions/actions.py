# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

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

class ActionAskClarification(Action):
    def name(self):
        return "action_ask_clarification"

    async def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(text="Sorry, I can't understand. Could you rephrase?")
        return [UserUtteranceReverted()]


class ActionListTopMovies(Action):
    def name(self) -> Text:
        return "action_list_top_movies"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Ottieni i 5 film con il rating più alto
        top_movies = movies_df.sort_values(by="IMDB_Rating", ascending=False).head(5)

        response = "🎬 Here are the top-rated movies in IMDB:\n\n"
        response += "\n".join([
            f"⭐ {row['Series_Title']} - Rating: {row['IMDB_Rating']}" 
            for _, row in top_movies.iterrows()
        ])

        dispatcher.utter_message(text=response)
        return []
    

class ActionAskDirectorMovie(Action):
    def name(self) -> str:
        return "action_ask_director"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        # Ottieni il nome del film dall'entità 'movie'
        movie_name = tracker.get_slot("movie")

        if not movie_name:
            dispatcher.utter_message(text="❓ Please tell me the movie you are asking about. 🎥")
            return [SlotSet('movie', None)]

        movie_row = movies_df[movies_df['Series_Title'].str.contains(movie_name, case=False, na=False)]
        
        if movie_row.empty:
            new_name, score = process.extractOne(movie_name, movies.tolist())
            if score > soglia_fuzzy:
                dispatcher.utter_message("You misspelled the name of the movie. Don't worry, I've got it! 😊✨")
                movie_row = movies_df[movies_df['Series_Title'].str.contains(new_name, case=False, na=False)]

        
        logging.info(f"MOVIE NAME: {movie_name}")
        if not movie_row.empty:
            if len(movie_row) > 1:
                message = "🔍 Multiple movies found matching your query:\n"
                for _, row in movie_row.iterrows():
                    message += f"🎬 {row['Series_Title']} - Directed by {row['Director']} 🌟\n"
                dispatcher.utter_message(text=message.strip())
            else:
                director = movie_row.iloc[0]['Director']
                dispatcher.utter_message(
                    text=f"🎬 The director of {movie_row.iloc[0]['Series_Title']} is {director}. 🌟"
                )
        else:
            dispatcher.utter_message(
                text=f"😔 I'm sorry, I couldn't find the movie {movie_name} or {new_name} in my database. 📂"
            )

        return [SlotSet('movie', None)]
    
class ActionAskGenre(Action):
    def name(self) -> str:
        return "action_ask_genre"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):

        movie_name = tracker.get_slot("movie")

        if not movie_name:
            dispatcher.utter_message(text="❓ I couldn't catch the name of the movie. Can you repeat it? 🎥")
            return [SlotSet('movie', None)]


        movie_row = movies_df[movies_df['Series_Title'].str.contains(movie_name, case=False, na=False)]

        if movie_row.empty:
            new_name, score = process.extractOne(movie_name, movies.tolist())
            if score > soglia_fuzzy:
                dispatcher.utter_message("You misspelled the movie. Don't worry, I've got it! 😊✨")
                movie_row = movies_df[movies_df['Series_Title'].str.contains(new_name, case=False, na=False)]


        if not movie_row.empty:
            alternatives = [
                f"🎞️ {row['Series_Title']} - Genre: {row['Genre']}" 
                for _, row in movie_row.iterrows()
            ]
            response = "🎬 Here are the genres for the matching movies:\n\n" + "\n".join(alternatives)
            dispatcher.utter_message(text=response)
        else:
            dispatcher.utter_message(
                text=f"😔 I'm sorry, I couldn't find the movie '{movie_name}' or '{new_name}' in my database. 📂"
            )

        return [SlotSet('movie', None)]
    
class ActionAskDirector(Action):
    def name(self) -> str:
        return "action_movies_by_director"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        # Ottieni il valore dello slot 'director'
        director = tracker.get_slot("director")
        
        if not director:
            dispatcher.utter_message(text="🎬 I couldn't catch the name of the director. Can you repeat it?")
            return [SlotSet('director', None)]

        # Cerca i film nel database per il regista
        dir_movies = movies_df[movies_df['Director'].str.contains(director, case=False, na=False)]
        
        if dir_movies.empty:
            new_name, score = process.extractOne(director, director_df.tolist())
            if score > soglia_fuzzy:
                dispatcher.utter_message("You misspelled the name of the director. Don't worry, I've got it! 😊✨")
                dir_movies = movies_df[movies_df['Director'].str.contains(new_name, case=False, na=False)]


        if not dir_movies.empty:
            # Creiamo una lista dei film del regista trovato
            movie_list = dir_movies['Series_Title'].tolist()
            movie_titles = '\n'.join([f"🎞️ {movie}" for movie in movie_list])  # Aggiungi un'icona a ogni titolo
            dispatcher.utter_message(
                text=f"🎥 The movies made by {director} are:\n{movie_titles}"
            )
        else:
            dispatcher.utter_message(
                text=f"😔 I'm sorry, I couldn't find any films by {director} or {new_name} in my database."
            )
        
        return [SlotSet('director', None)]


class ActionAskActor(Action):
    def name(self) -> str:
        return "action_movies_by_actor"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        # Ottieni il valore dello slot 'actor'
        actor_name = tracker.get_slot("actor")
        original_actor_name = actor_name  # Per mantenere il valore originale

        if not actor_name:
            dispatcher.utter_message(text="I couldn't catch the name of the actor. Can you repeat it?")
            return [SlotSet('actor', None)]

        # Cerca i film in cui l'attore appare in uno dei ruoli (Star1, Star2, Star3, Star4)
        actor_movies = movies_df[
            (movies_df['Star1'].str.contains(actor_name, case=False, na=False)) |
            (movies_df['Star2'].str.contains(actor_name, case=False, na=False)) |
            (movies_df['Star3'].str.contains(actor_name, case=False, na=False)) |
            (movies_df['Star4'].str.contains(actor_name, case=False, na=False))
        ]

        if actor_movies.empty:
            # Utilizziamo il fuzzy matching per correggere eventuali errori
            all_actors = (
                movies_df['Star1'].dropna().tolist() +
                movies_df['Star2'].dropna().tolist() +
                movies_df['Star3'].dropna().tolist() +
                movies_df['Star4'].dropna().tolist()
            )
            all_actors = list(set(all_actors))  # Eliminiamo i duplicati
            corrected_name, score = process.extractOne(actor_name, all_actors)

            if score > 85:  # Soglia per considerare una correzione accettabile
                actor_name = corrected_name
                dispatcher.utter_message(text=f"Did you mean '{actor_name}'? Don't worry, I've found the information for you! 😊")
                # Ricerchiamo di nuovo con il nome corretto
                actor_movies = movies_df[
                    (movies_df['Star1'].str.contains(actor_name, case=False, na=False)) |
                    (movies_df['Star2'].str.contains(actor_name, case=False, na=False)) |
                    (movies_df['Star3'].str.contains(actor_name, case=False, na=False)) |
                    (movies_df['Star4'].str.contains(actor_name, case=False, na=False))
                ]

        if not actor_movies.empty:
            # Troviamo il nome completo dell'attore
            matching_actors = actor_movies[['Star1', 'Star2', 'Star3', 'Star4']].stack().unique()
            full_name = next((name for name in matching_actors if actor_name.lower() in name.lower()), actor_name)

            # Creiamo una lista dei film in cui l'attore è apparso
            movie_list = actor_movies['Series_Title'].tolist()
            movie_titles = '\n'.join([f"🎬 {movie}" for movie in movie_list])  # Aggiungiamo l'icona a ogni titolo
            dispatcher.utter_message(text=f"🌟 The films featuring {full_name} are:\n{movie_titles}")
        else:
            dispatcher.utter_message(text=f"😔 I'm sorry, I couldn't find any films featuring '{original_actor_name}' or '{actor_name}' in my database.")

        return [SlotSet('actor', None)]


class ActionAskMovieInfo(Action):
    def name(self) -> str:
        return "action_ask_movie_info"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Ottieni il nome del film dallo slot 'movie'
        movie_name = tracker.get_slot("movie")
        first_name = movie_name

        if not movie_name:
            dispatcher.utter_message(text="I couldn't catch the name of the movie. Can you repeat it?")
            return [SlotSet('movie', None)]

        # Cerca il film nel database
        movie_row = movies_df[movies_df['Series_Title'].str.contains(movie_name, case=False, na=False)]

        if movie_row.empty:         
            new_name, score = process.extractOne(movie_name, movies_df['Series_Title'].tolist())
            logging.info(f"Somiglianza del {score}")
            if score > soglia_fuzzy:
                dispatcher.utter_message("You misspelled the title. Don't worry, I've got it! 😊✨")
                movie_row = movies_df[movies_df['Series_Title'].str.contains(new_name, case=False, na=False)]

        if not movie_row.empty:
            # Estrai tutte le informazioni desiderate
            movie = movie_row.iloc[0]
            title = movie['Series_Title']
            genre = movie['Genre']
            year = movie['Released_Year']
            rating = movie['IMDB_Rating']
            overview = movie['Overview']
            director = movie['Director']
            stars = movie[['Star1', 'Star2', 'Star3', 'Star4']].dropna().values
            runtime = movie['Runtime']

            # Costruisci la risposta
            stars_list = ', '.join(stars) if len(stars) > 0 else "No stars listed."

            response = (
                f"🎥 Here are the details for the movie '{title}':\n"
                f"🎭 Genre: {genre}\n"
                f"⏳ Runtime: {runtime}\n"
                f"📅 Release Year: {year}\n"
                f"⭐ Rating: {rating}/10\n"
                f"🎬 Director: {director}\n"
                f"🌟 Stars: {stars_list}\n"
                f"📝 Overview: {overview}"
            )


            dispatcher.utter_message(text=response)
            dispatcher.utter_message(image=movie['Poster_Link'])
        else:
            dispatcher.utter_message(text=f"I'm sorry, I couldn't find any information about the movie '{first_name}' or '{movie_name}' in my database.")

        return [SlotSet('movie', None)]

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

        
class ActionCheckFormSlots(Action):

    def name(self) -> str:
        return "action_check_form_slots"
    
    def run(self, dispatcher, tracker, domain):
        # Controlla se gli slot sono stati compilati
        form_director_genre = tracker.get_slot('form_director_genre')
        form_quality = tracker.get_slot('form_quality')

        # Se lo slot non è stato fornito, lo settiamo su None
        if form_director_genre is None:
            form_director_genre = "None"
        if form_quality is None:
            form_quality = "None"

        # Restituire gli eventi
        return [SlotSet("form_director_genre", form_director_genre),
                SlotSet("form_quality", form_quality)]
    

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
    

class ActionRemoveUnnecessarySlots(Action):
    def name(self) -> Text:
        return "action_remove_unnecessary_slots"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[SlotSet]:
        # Definisci gli slot da ignorare
        logging.info("DENTRO: action_remove_unnecessary_slots")
        unnecessary_slots = ["form_author", "form_genre", "movie" ]

        # Rimuovi i valori per gli slot non necessari
        events = []
        for slot in unnecessary_slots:
            if tracker.get_slot(slot) is not None:
                events.append(SlotSet(slot, None))
        
        return events
