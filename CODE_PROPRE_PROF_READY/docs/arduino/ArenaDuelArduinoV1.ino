#include <Wire.h>
#include <LiquidCrystal_I2C.h>

const uint8_t LCD_I2C_ADDRESS = 0x27;
const uint8_t LCD_COLUMNS = 16;
const uint8_t LCD_ROWS = 2;

const uint8_t STATUS_LED_PIN = 7;
const uint8_t BUZZER_PIN = 8;

const unsigned long COMBAT_BLINK_MS = 250;
const unsigned long LOBBY_BLINK_MS = 900;

LiquidCrystal_I2C lcd(LCD_I2C_ADDRESS, LCD_COLUMNS, LCD_ROWS);

String currentState = "LOBBY";
String currentWinner = "DRAW";
String incomingLine = "";
int scoreA = 0;
int scoreB = 0;
bool ledState = false;
unsigned long lastBlinkAtMs = 0;

void setup() {
  pinMode(STATUS_LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);
  noTone(BUZZER_PIN);

  Serial.begin(115200);

  lcd.init();
  lcd.backlight();
  renderBootScreen();
  delay(600);
  resetMatchState();
  renderScreen();
}

void loop() {
  readSerialProtocol();
  updateStatusLed();
}

void readSerialProtocol() {
  while (Serial.available() > 0) {
    char readChar = static_cast<char>(Serial.read());

    if (readChar == '\r') {
      continue;
    }

    if (readChar == '\n') {
      handleProtocolLine(incomingLine);
      incomingLine = "";
      continue;
    }

    incomingLine += readChar;
  }
}

void handleProtocolLine(String line) {
  line.trim();
  if (line.length() == 0) {
    return;
  }

  if (line == "RESET") {
    resetMatchState();
    renderScreen();
    return;
  }

  if (line.startsWith("STATE:")) {
    currentState = line.substring(6);
    currentState.trim();
    currentState.toUpperCase();
    renderScreen();
    return;
  }

  if (line.startsWith("SCORE:")) {
    parseScore(line.substring(6));
    renderScreen();
    return;
  }

  if (line.startsWith("WINNER:")) {
    currentWinner = line.substring(7);
    currentWinner.trim();
    currentWinner.toUpperCase();
    currentState = "RESULT";
    renderScreen();
    playWinnerTone();
    return;
  }
}

void parseScore(String payload) {
  int separatorIndex = payload.indexOf(',');
  if (separatorIndex < 0) {
    return;
  }

  scoreA = payload.substring(0, separatorIndex).toInt();
  scoreB = payload.substring(separatorIndex + 1).toInt();
}

void resetMatchState() {
  currentState = "LOBBY";
  currentWinner = "DRAW";
  scoreA = 0;
  scoreB = 0;
}

void renderBootScreen() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(padRight("Arena Duel", LCD_COLUMNS));
  lcd.setCursor(0, 1);
  lcd.print(padRight("Bridge Arduino", LCD_COLUMNS));
}

void renderScreen() {
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print(buildFirstRow());

  lcd.setCursor(0, 1);
  lcd.print(buildSecondRow());
}

String buildFirstRow() {
  if (currentState == "RESULT") {
    if (currentWinner == "A") {
      return padRight("Victoire A", LCD_COLUMNS);
    }
    if (currentWinner == "B") {
      return padRight("Victoire B", LCD_COLUMNS);
    }
    return padRight("Match nul", LCD_COLUMNS);
  }

  String stateLabel = currentState;
  if (stateLabel.length() > 6) {
    stateLabel = stateLabel.substring(0, 6);
  }
  return padRight(stateLabel + " " + String(scoreA) + "-" + String(scoreB), LCD_COLUMNS);
}

String buildSecondRow() {
  if (currentState == "RESULT") {
    return padRight("Score " + String(scoreA) + "-" + String(scoreB), LCD_COLUMNS);
  }

  if (currentState == "COMBAT") {
    return padRight("LCD+Buzzer OK", LCD_COLUMNS);
  }

  return padRight("Pret pour duel", LCD_COLUMNS);
}

void updateStatusLed() {
  unsigned long now = millis();

  if (currentState == "RESULT") {
    digitalWrite(STATUS_LED_PIN, HIGH);
    return;
  }

  unsigned long blinkDelay = currentState == "COMBAT"
    ? COMBAT_BLINK_MS
    : LOBBY_BLINK_MS;

  if (now - lastBlinkAtMs < blinkDelay) {
    return;
  }

  lastBlinkAtMs = now;
  ledState = !ledState;
  digitalWrite(STATUS_LED_PIN, ledState ? HIGH : LOW);
}

void playWinnerTone() {
  tone(BUZZER_PIN, 988, 120);
  delay(160);
  tone(BUZZER_PIN, 1319, 140);
  delay(180);
  tone(BUZZER_PIN, 1568, 200);
  delay(220);
  noTone(BUZZER_PIN);
}

String padRight(String value, uint8_t width) {
  if (value.length() >= width) {
    return value.substring(0, width);
  }

  while (value.length() < width) {
    value += " ";
  }
  return value;
}