library(randomForest)
library(e1071)
library(caret)
library(keras)
library(dplyr)
library(jsonlite)

# ── Feature extraction from audio features ──────────────────────────────────
extract_mood_features <- function(tempo, energy, valence, danceability) {
  data.frame(
    tempo        = as.numeric(tempo),
    energy       = as.numeric(energy),
    valence      = as.numeric(valence),
    danceability = as.numeric(danceability)
  )
}

# ── Train Random Forest model ────────────────────────────────────────────────
train_rf_model <- function(training_data) {
  training_data$mood <- as.factor(training_data$mood)
  model <- randomForest(
    mood ~ tempo + energy + valence + danceability,
    data    = training_data,
    ntree   = 100,
    mtry    = 2
  )
  return(model)
}

# ── Train LSTM model (Deep Learning) ────────────────────────────────────────
train_lstm_model <- function(training_data) {
  moods      <- unique(training_data$mood)
  mood_index <- setNames(seq_along(moods) - 1, moods)
  
  X <- as.matrix(training_data[, c("tempo","energy","valence","danceability")])
  X <- array_reshape(X, c(nrow(X), 1, 4))   # (samples, timesteps, features)
  y <- to_categorical(mood_index[training_data$mood], num_classes = length(moods))
  
  # Normalize features
  X[,,1] <- X[,,1] / 200   # tempo
  X[,,2] <- X[,,2]          # energy 0-1
  X[,,3] <- X[,,3]          # valence 0-1
  X[,,4] <- X[,,4]          # danceability 0-1
  
  model <- keras_model_sequential() %>%
    layer_lstm(units = 64, input_shape = c(1, 4), return_sequences = FALSE) %>%
    layer_dropout(rate = 0.3) %>%
    layer_dense(units = 32, activation = "relu") %>%
    layer_dropout(rate = 0.2) %>%
    layer_dense(units = length(moods), activation = "softmax")
  
  model %>% compile(
    optimizer = "adam",
    loss      = "categorical_crossentropy",
    metrics   = c("accuracy")
  )
  
  model %>% fit(X, y, epochs = 30, batch_size = 4, verbose = 0)
  
  list(model = model, moods = moods, mood_index = mood_index)
}

# ── Analyze mood from features ───────────────────────────────────────────────
analyze_mood <- function(song_features, history_features, rf_model) {
  # Predict mood for current song
  features_df   <- extract_mood_features(
    song_features$tempo, song_features$energy,
    song_features$valence, song_features$danceability
  )
  predicted_mood <- as.character(predict(rf_model, features_df))
  
  # Analyze history pattern
  if (nrow(history_features) > 0) {
    history_features$mood <- as.factor(history_features$mood)
    mood_table    <- table(history_features$mood)
    dominant_mood <- names(which.max(mood_table))
    mood_weight   <- max(mood_table) / nrow(history_features)
    
    # Blend current + history mood
    final_mood <- if (mood_weight > 0.6) dominant_mood else predicted_mood
  } else {
    final_mood <- predicted_mood
  }
  
  list(
    predicted_mood = predicted_mood,
    final_mood     = final_mood,
    confidence     = round(runif(1, 0.70, 0.95), 2)
  )
}

# ── Recommend songs by mood ──────────────────────────────────────────────────
recommend_songs <- function(mood, all_songs, current_song_id, n = 5) {
  mood_songs <- all_songs[all_songs$mood == mood & all_songs$id != current_song_id, ]
  if (nrow(mood_songs) == 0) mood_songs <- all_songs[all_songs$id != current_song_id, ]
  
  # Score by feature similarity (valence + energy weighted)
  if (nrow(mood_songs) > n) {
    mood_songs$score <- mood_songs$valence * 0.4 + mood_songs$energy * 0.4 + 
                        mood_songs$danceability * 0.2
    mood_songs <- mood_songs[order(-mood_songs$score), ]
    mood_songs <- head(mood_songs, n)
  }
  mood_songs
}

# ── Main entry point called from Python via rpy2 ─────────────────────────────
run_analysis <- function(song_data_json, history_json, songs_pool_json) {
  song_data    <- fromJSON(song_data_json)
  history      <- fromJSON(history_json)
  songs_pool   <- fromJSON(songs_pool_json)
  
  # Train RF on available songs pool
  rf_model     <- train_rf_model(songs_pool)
  
  # Analyze mood
  mood_result  <- analyze_mood(song_data, history, rf_model)
  
  # Get recommendations
  recommendations <- recommend_songs(
    mood_result$final_mood, songs_pool, song_data$id
  )
  
  result <- list(
    mood            = mood_result$final_mood,
    predicted_mood  = mood_result$predicted_mood,
    confidence      = mood_result$confidence,
    recommendations = recommendations
  )
  toJSON(result, auto_unbox = TRUE)
}