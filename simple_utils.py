# simple_utils.py - A tiny utility library

def reverse_string(text):
    """
    Reverses the characters in a string.
    
    Args:
        text: The string to be reversed.
    
    Returns:
        A new string with the characters of text in reverse order.
    """
    return text[::-1]

def count_words(sentence):
    """
    Counts the number of words in a sentence.
    
    Args:
    	sentence: The input string to analyze.
    
    Returns:
    	The number of words separated by whitespace.
    """
    return len(sentence.split())

def celsius_to_fahrenheit(celsius):
    """
    Converts a temperature from Celsius to Fahrenheit.
    
    Args:
    	celsius: Temperature value in degrees Celsius.
    
    Returns:
    	The equivalent temperature in degrees Fahrenheit.
    """
    return (celsius * 9/5) + 32
