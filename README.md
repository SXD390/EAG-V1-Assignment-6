# 🍳 Smart Kitchen Assistant

A sophisticated AI-powered kitchen assistant that helps users manage recipes, ingredients, and grocery shopping seamlessly. The assistant uses a cognitive architecture to process user inputs, manage recipes, check pantry items, order missing ingredients, and send email confirmations.

## 🌟 High-Level Overview

The Smart Kitchen Assistant is an intelligent agent that:
- 🔍 Finds recipes based on user requests(as of now only a dozen recipies are available as per static coding)
- 📝 Checks available ingredients in user's pantry against recipe requirements
- 🛒 Automatically orders missing ingredients
- 📧 Sends email confirmations for orders
- 👩‍🍳 Provides step-by-step cooking instructions

## 🏗️ Technical Implementation

### Architecture Components

1. **Cognitive Layers**
   - `PerceptionLayer`: Handles user input and interaction
   - `MemoryLayer`: Manages state and persistence
   - `DecisionLayer`: Determines next actions
   - `ActionLayer`: Executes determined actions

2. **MCP Servers**
   - `recipe_mcp_server.py`: Manages recipe database and ingredient comparison
   - `delivery_mcp_server.py`: Handles order placement and tracking
   - `gmail_mcp_server.py`: Manages email notifications

3. **Core Components**
   - `main.py`: Orchestrates the entire process
   - `models.py`: Defines data structures and type definitions

### Process Flow

```mermaid
graph TD
    A[Start] --> B{Has Dish Name?}
    B -->|No| C[Get Dish Name from User]
    B -->|Yes| D{Has Recipe?}
    C --> D
    
    D -->|No| E[Fetch Recipe]
    D -->|Yes| F{Has Pantry Items?}
    E --> F
    
    F -->|No| G[Get Pantry Items from User]
    F -->|Yes| H{Missing Ingredients?}
    G --> H
    
    H -->|Yes| I{Has User Email?}
    H -->|No| M[Display Recipe]
    I -->|No| J[Get User Email]
    I -->|Yes| K[Place Order]
    
    J --> K
    K --> L[Send Email Confirmation]
    L --> M
    
    style A fill:#f9d71c,stroke:#333,stroke-width:2px,color:#000
    style B fill:#87ceeb,stroke:#333,stroke-width:2px,color:#000
    style C fill:#98fb98,stroke:#333,stroke-width:2px,color:#000
    style D fill:#87ceeb,stroke:#333,stroke-width:2px,color:#000
    style E fill:#98fb98,stroke:#333,stroke-width:2px,color:#000
    style F fill:#87ceeb,stroke:#333,stroke-width:2px,color:#000
    style G fill:#98fb98,stroke:#333,stroke-width:2px,color:#000
    style H fill:#87ceeb,stroke:#333,stroke-width:2px,color:#000
    style I fill:#87ceeb,stroke:#333,stroke-width:2px,color:#000
    style J fill:#98fb98,stroke:#333,stroke-width:2px,color:#000
    style K fill:#ffa07a,stroke:#333,stroke-width:2px,color:#000
    style L fill:#dda0dd,stroke:#333,stroke-width:2px,color:#000
    style M fill:#90ee90,stroke:#333,stroke-width:2px,color:#000
```

### PADM Architecture Flow

```mermaid
graph TD
    subgraph Perception[Perception Layer]
        P1[User Input Handler] --> P2[Input Parser]
        P2 --> P3[Input Validator]
    end

    subgraph Memory[Memory Layer]
        M1[State Manager] --> M2[Persistence Handler]
        M2 --> M3[Context Provider]
    end

    subgraph Decision[Decision Layer]
        D1[Action Planner] --> D2[State Analyzer]
        D2 --> D3[Next Action Determiner]
    end

    subgraph Action[Action Layer]
        A1[Recipe Service] --> A2[Delivery Service]
        A2 --> A3[Email Service]
    end

    P3 --> M1
    M3 --> D1
    D3 --> A1

    style Perception fill:#ffe4b5,stroke:#333,stroke-width:2px,color:#000
    style Memory fill:#b0e0e6,stroke:#333,stroke-width:2px,color:#000
    style Decision fill:#dda0dd,stroke:#333,stroke-width:2px,color:#000
    style Action fill:#98fb98,stroke:#333,stroke-width:2px,color:#000
    
    style P1 fill:#fff,stroke:#333,stroke-width:1px,color:#000
    style P2 fill:#fff,stroke:#333,stroke-width:1px,color:#000
    style P3 fill:#fff,stroke:#333,stroke-width:1px,color:#000
    
    style M1 fill:#fff,stroke:#333,stroke-width:1px,color:#000
    style M2 fill:#fff,stroke:#333,stroke-width:1px,color:#000
    style M3 fill:#fff,stroke:#333,stroke-width:1px,color:#000
    
    style D1 fill:#fff,stroke:#333,stroke-width:1px,color:#000
    style D2 fill:#fff,stroke:#333,stroke-width:1px,color:#000
    style D3 fill:#fff,stroke:#333,stroke-width:1px,color:#000
    
    style A1 fill:#fff,stroke:#333,stroke-width:1px,color:#000
    style A2 fill:#fff,stroke:#333,stroke-width:1px,color:#000
    style A3 fill:#fff,stroke:#333,stroke-width:1px,color:#000
```

The PADM architecture diagram shows how the four cognitive layers interact:
1. **Perception Layer**: Handles all user inputs, validates them, and prepares them for processing
2. **Memory Layer**: Manages application state, persists data, and provides context for decision making
3. **Decision Layer**: Analyzes current state and determines next actions based on the system's goals
4. **Action Layer**: Executes actions through various services (Recipe, Delivery, Email)

### Detailed Implementation

#### 1. Initialization
- Environment setup using `.env` file
- MCP server initialization
- Cognitive layer initialization
- Memory state initialization

#### 2. User Interaction Flow
1. **Recipe Selection**
   - User provides dish name
   - System fetches recipe details
   - Recipe stored in memory

2. **Ingredient Management**
   - System lists required ingredients
   - User indicates available ingredients
   - System identifies missing items

3. **Order Processing**
   - System collects user email
   - Places order for missing ingredients
   - Sends confirmation email

4. **Recipe Presentation**
   - Displays complete ingredient list
   - Shows step-by-step instructions
   - Indicates which items were ordered

#### 3. Memory Management
- Persistent storage using JSON
- State tracking across sessions
- Real-time updates during process

#### 4. Error Handling
- Input validation
- Service availability checks
- Graceful error recovery
- User feedback for issues

## 🛠️ Technical Requirements

- Python 3.8+
- Required packages:
  - `mcp`: For server communication
  - `google-auth`: For Gmail integration
  - `python-dotenv`: For environment management
  - `colorama`: For colored console output

## 📁 Project Structure

```
Assignment/
├── main.py                    # Main orchestration script
├── models.py                  # Core data models and types
├── perception.py             # Perception layer implementation
├── memory.py                 # Memory layer implementation
├── decision.py              # Decision layer implementation
├── action.py                # Action layer implementation
├── MCP_SERVERS/             # MCP server implementations
│   ├── recipe_mcp_server.py
│   ├── delivery_mcp_server.py
│   ├── gmail_mcp_server.py
│   └── models.py            # Server-specific models
├── credentials/             # Configuration and authentication
│   ├── .env                # Environment variables
│   ├── credentials.json    # Gmail API credentials
│   └── token.json         # Gmail API tokens
└── MEMORY/                 # Persistent storage
    └── agent_memory.json   # Agent's memory state
```

## 🚀 Getting Started

1. Clone the repository
2. Set up credentials in `credentials/` directory
3. Install dependencies: `pip install -r requirements.txt`
4. Run the assistant: `python main.py`

## 🔐 Environment Setup

Required environment variables in `.env`:
```
GEMINI_API_KEY=your_api_key_here
```

## 📝 Usage Example

```bash
$ python main.py
> What would you like to cook? chicken curry
> Which ingredients do you have? chicken breast, onion, ginger, curry powder
> Please provide your email: user@example.com
> Order placed! Check your email for confirmation.
> Here are your cooking instructions...
``` 