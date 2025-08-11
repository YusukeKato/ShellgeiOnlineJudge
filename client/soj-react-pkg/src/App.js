import black_tree_icon from './BlackTreeIcon.jpg';
import './App.css';
import AboutPage from './test.jsx';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <img src={black_tree_icon} className="App-logo" alt="logo" />
        <p>
          Edit <code>src/App.js</code> and save to reload.
        </p>
        <AboutPage />
        <a
          className="App-link"
          href="https://reactjs.org"
          target="_blank"
          rel="noopener noreferrer"
        >
          Learn React
        </a>
      </header>
    </div>
  );
}

export default App;
