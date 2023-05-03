import argparse
import os
import random
import openai
from genanki import Deck, Model, Package, Note
import pdfplumber
import json

ANKI_MODEL = Model(
    model_id=random.randrange(1 << 30, 1 << 31),
    name="Pdf to Anki",
    fields=[{"name": "Question"}, {"name": "Answer"}],
    templates=[
        {
            "name": "Card",
            'qfmt': '{{Question}}',
            'afmt': '{{FrontSide}}<hr id="answer">{{Answer}}',
        }
    ],
)


def parse_command_line_arguments():
    parser = argparse.ArgumentParser(
        description='Converts a PDF into an Anki deck with the help of the OpenAI API.')
    parser.add_argument('--pdf-input', help='path to the input PDF file', required=True)
    parser.add_argument('--out-dir', help='output directory of the .apkg file (Anki deck)', default='./',
                        required=False)
    parser.add_argument('--anki-file-name', help='name of the resulting .apkg file', default='Deck',
                        required=False)
    parser.add_argument('--deck-name', help='name of the Deck', default='Deck',
                        required=False)
    parser.add_argument('--openai-api-key', help='OpenAI API key', required=True)
    parser.add_argument('--openai-organization-id', help='OpenAI organization ID', required=True)
    parser.add_argument('--chatgpt-model', help='GPT model', default='gpt-3.5-turbo', required=False)
    parser.add_argument('--max-num-words', help='maximum number of words', default=1000, required=False)
    parser.add_argument('--chatgpt-prompt', help='GPT prompt',
                        default='Use the provided text to generate Anki flashcards. Generate the flashcards as a JSON array with the keys "front" (question) and "back" (answer). Just generate the JSON string and no unnecessary text. Text: {}',
                        required=False)

    return parser.parse_args()


def handle_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"An error occurred: {e}")
            exit(1)

    return wrapper


def main():
    args = parse_command_line_arguments()

    if not os.path.isfile(args.pdf_input):
        raise FileNotFoundError(f"The PDF file '{args.pdf_input}' does not exist.")

    if not os.path.exists(args.out_dir):
        os.makedirs(args.out_dir)

    openai.api_key = args.openai_api_key

    text = ""
    with pdfplumber.open(args.pdf_input) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text

    num_words = len(text.split())
    if num_words > args.max_num_words:
        raise ValueError(f"PDF exceeds {args.max_num_words} words.")

    print(f'initiating openai request ...')
    completion = openai.ChatCompletion.create(
        model=args.chatgpt_model,
        messages=[{'role': 'user', 'content': args.chatgpt_prompt.format(text)}],
        organization=args.openai_organization_id,
    )

    generated_text = completion.choices[0].message.content
    print(f'received openai response: {generated_text}')

    try:
        anki_cards_data = json.loads(generated_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from generated text: {e}")

    deck = Deck(random.randrange(1 << 30, 1 << 31), args.deck_name)
    for card_data in anki_cards_data:
        front = card_data.get("front")
        back = card_data.get("back")
        if not front or not back:
            continue
        card = Note(ANKI_MODEL, fields=[front, back])
        deck.add_note(card)

    dest = os.path.join(args.out_dir, f'{args.anki_file_name}.apkg')
    anki_package = Package(deck)
    anki_package.write_to_file(dest)
    print(f'saved deck "{args.deck_name}" at {dest}')


if __name__ == "__main__":
    main()
